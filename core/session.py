"""Oturum istatistikleri, tur ve sektor takibi, rekor gonderimi.

Dogruluk kurallari (kullanici onceligi: yanlis veri gostermektense hic gostermemek):
 * Tur suresi yalnizca oyunun kendi verdigi 'son tur suresi' alanindan alinir.
 * Tur ilk tamamlandiginda oyun alani hemen guncellenmeyebilir: yeni deger gelene kadar (<=1.5 sn)
   beklenir; gelmezse o tur KAYDEDILMEZ.
 * Oyun kendi saatini veriyorsa tur suresi, tur sayaci degisimleri arasindaki oyun saatiyle capraz
   dogrulanir (+-0.4 sn); uyusmazsa kaydedilmez.
 * PitApex bir turun ortasinda baslatildiysa o ilk (kismi) tur kaydedilmez.
 * Pit yolu kullanilan, oyunca gecersiz isaretlenen veya supheli turlar kaydedilmez.
 * Sektor sureleri: oyun tam sektor verdiyse (LMU) ya da sektor gecis anlarinda oyunun sektor
   alani oyunun kendi tur saatiyle dogrulanabildiyse kullanilir. Dogrulanamazsa None.
   S1+S2+S3 tur suresine +-2 ms uymuyorsa hepsi atilir.
 * Tur olaylari: BASLANGIC (yeni tur dogar), TAMAMLANMA (oyun tur sayaci +1), SIFIRLAMA (sayac geriye gider ya da
   tur saati ayni sayacta geri sarar: pite donus / tur yeniden baslatma). Sifirlanan tur ASLA kaydedilmez ve
   eski turun bayraklari, saati, sektorleri yeni tura tasinmaz.
 * Tur suresi, bitisten onceki son tur saati okumasiyla (oyunun anlik tur sayaci) da capraz dogrulanir.
 * Tur sayaci hic sifirlanmiyorsa (tur suresi sinirsiz buyuyorsa) o tur 'asiri uzun' sayilir ve kaydedilmez."""
import threading
import time
import uuid

from core.models import fmt_ms
from storage.records import MAX_LAP_MS, MIN_LAP_MS

PEND_TIMEOUT = 1.5
CLOCK_TOL_MS = 400
SECTOR_WINDOW = (-80, 300)       # sektor gecisinden sonra tur saati - sektor suresi araligi (ms)
MIN_SECTOR_MS = 2000
CHECKPOINT_S = 60
REWIND_TOL_MS = 1000             # tur saati bu kadar geri giderse sayac sifirlanmis sayilir
REWIND_GRACE_S = 0.6             # geri sarma + tur sayaci artisi bu sure icinde gelirse normal tur bitisidir
BIRTH_GRACE_S = 1.5              # yeni dogan turda tur saati / sektor gostergesinin eski degerden toparlanma suresi
CUR_TOL_MS = 600                 # bitis oncesi son tur saati okumasi ile bildirilen sure arasindaki izin
MAX_LAP_S = MAX_LAP_MS / 1000.0


def _iso(t=None):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


class SessionTracker:
    def __init__(self, records, sessions, game_names):
        self.records = records
        self.sessions = sessions
        self.game_names = game_names
        self.lock = threading.RLock()
        self.ctx = None
        self.sess = None
        self.rec_at_start = None
        self.prev_session = None
        self.lap = None
        self.pend = None
        self.last_t = None
        self.last_ckpt = 0.0
        self.last_event = ""
        self.live = False
        self.lap_tracking = False
        self.acc = {}
        self.ended = False           # True: oturum bitti (oyun kapandi) ama EKRANDA korunuyor, yeni oturuma kadar
        self.last_state = None       # son canli karedeki degerler (baglanti kesilince gosterilmeye devam eder)
        self._restore()

    # ---------------- oturum ----------------
    _STATE_FIELDS = ("speed_kmh", "rpm", "throttle", "brake", "gear", "abs_active", "tc_active", "abs_level",
                     "tc_level", "fuel_l", "water_c", "oil_c", "tyre_temp_c", "tyre_press_kpa", "engine_running",
                     "track_name", "car_name")

    def _restore(self):
        """Uygulama yeniden acildiginda en son oturumu (ve son telemetri degerlerini) ekranda goster.
        Yeni bir oturum baslayana kadar korunur; sonra arsivde kalir."""
        try:
            recent = self.sessions.recent(1)
        except Exception:
            return
        if not recent:
            return
        s = recent[0]
        s.setdefault("lap_times_ms", [])
        s.setdefault("best_sectors_ms", [None, None, None])
        self.sess = s
        self.ended = True
        self.last_state = s.get("last_state")

    def _capture(self, f):
        st = {k: getattr(f, k, None) for k in self._STATE_FIELDS}
        for k in ("tyre_temp_c", "tyre_press_kpa"):
            if st[k] is not None:
                st[k] = list(st[k])
        st["t"] = _iso()
        self.last_state = st

    def _new_acc(self):
        return {"move_t": 0.0, "speed_sum": 0.0, "max_speed": None, "max_rpm": None,
                "thr_t": 0.0, "thr_sum": 0.0, "brk_t": 0.0, "brk_sum": 0.0}

    def _start_session(self, f, ctx, now):
        game_id = f.game
        sid = "%s-%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), game_id, uuid.uuid4().hex[:6])  # ayni saniyede de benzersiz
        self.sess = {
            "id": sid, "game_id": game_id, "game_name": self.game_names.get(game_id, game_id),
            "track_id": f.track_id, "track_name": f.track_name, "car_id": f.car_id, "car_name": f.car_name,
            "started": _iso(), "updated": _iso(), "laps_completed": 0, "valid_laps": 0,
            "lap_times_ms": [], "lap_history": [], "driving_seconds": 0.0, "session_type": None, "best_lap_ms": None, "best_sectors_ms": [None, None, None],
        }
        self.ctx = ctx
        self.ended = False
        self.last_state = None
        self.acc = self._new_acc()
        self.lap = None
        self.pend = None
        self.last_t = None
        self.prev_session = self.sessions.latest_for(game_id, f.track_id, f.car_id, exclude_id=sid)
        self.last_event = ""
        self.last_ckpt = now

    def _summary(self):
        s = self.sess
        a = self.acc
        lt = s["lap_times_ms"]
        s["driving_seconds"] = round(a["move_t"], 1)
        s["avg_lap_ms"] = int(round(sum(lt) / len(lt))) if lt else None
        s["avg_speed_kmh"] = a["speed_sum"] / a["move_t"] if a["move_t"] > 1 else None
        s["max_speed_kmh"] = a["max_speed"]
        s["max_rpm"] = a["max_rpm"]
        s["throttle_avg_pct"] = 100 * a["thr_sum"] / a["thr_t"] if a["thr_t"] > 1 else None
        s["brake_avg_pct"] = 100 * a["brk_sum"] / a["brk_t"] if a["brk_t"] > 1 else None
        b = s["best_sectors_ms"]
        s["theoretical_best_ms"] = sum(b) if all(x is not None for x in b) else None
        s["updated"] = _iso()

    def _persist(self):
        if not self.sess:
            return
        self._summary()
        out = dict(self.sess)
        out["lap_times_ms"] = list(out["lap_times_ms"][-300:])
        out["lap_history"] = list(out.get("lap_history", [])[-500:])
        out["best_sectors_ms"] = list(out["best_sectors_ms"])
        out["last_state"] = dict(self.last_state) if self.last_state else None
        # hic veri toplanmamis (tur yok, hareket yok) oturumlar gurultu yaratmasin
        if out["laps_completed"] == 0 and self.acc["move_t"] < 5:
            return
        self.sessions.upsert(out)

    def end(self):
        """Oyun kapandi / uygulama kapaniyor: oturumu kaydet ve KAPAT. Oturumun verileri silinmez:
        ekranda (ended=True) yeni oturum baslayana kadar gorunmeye devam eder."""
        with self.lock:
            if self.sess and not self.ended:
                self.sess["ended_at"] = _iso()
                self._persist()
                self.ended = True
            self.ctx = None
            self.lap = None
            self.pend = None
            self.last_t = None
            self.live = False
            self.lap_tracking = False

    def reset_all(self):
        """Veri temizlendi (kullanici onayiyla): bellekteki oturumu kayit yazmadan birak."""
        with self.lock:
            self.sess = None
            self.ctx = None
            self.lap = None
            self.pend = None
            self.prev_session = None
            self.last_event = ""
            self.ended = False
            self.last_state = None

    # ---------------- ana giris ----------------
    def update(self, f, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if f is None or not f.live:
                self.live = False
                self.last_t = None
                return
            self.live = True
            if not f.track_id or not f.car_id:
                self.lap_tracking = False      # pist/arac bilinmiyor: oturum ve rekor takibi yok
                return
            ctx = (f.game, f.track_id, f.car_id)
            if ctx != self.ctx:
                if self.sess and not self.ended:
                    self._persist()           # onceki oturum arsivde kalir (silinmez)
                self._start_session(f, ctx, now)
            self._capture(f)
            self._accumulate(f)
            self._laps(f, now)
            if now - self.last_ckpt > CHECKPOINT_S:
                self.last_ckpt = now
                self._persist()

    def _accumulate(self, f):
        a = self.acc
        dt = None if self.last_t is None else f.t - self.last_t
        self.last_t = f.t
        if f.speed_kmh is not None:
            a["max_speed"] = f.speed_kmh if a["max_speed"] is None else max(a["max_speed"], f.speed_kmh)
        if f.rpm is not None:
            a["max_rpm"] = f.rpm if a["max_rpm"] is None else max(a["max_rpm"], f.rpm)
        if dt is None or not (0 < dt <= 0.25):
            return
        if f.speed_kmh is not None and f.speed_kmh > 5:
            a["move_t"] += dt
            a["speed_sum"] += f.speed_kmh * dt
            if f.throttle is not None:
                a["thr_t"] += dt
                a["thr_sum"] += f.throttle * dt
            if f.brake is not None:
                a["brk_t"] += dt
                a["brk_sum"] += f.brake * dt

    # ---------------- tur takibi ----------------
    @staticmethod
    def _lap_start_clock(f):
        """Bu turun basladigi andaki oyun saati (oyun saati ve tur saati varsa)."""
        if f.clock_s is None:
            return None
        if f.lap_current_ms is not None and 0 <= f.lap_current_ms < 3_600_000:
            return f.clock_s - f.lap_current_ms / 1000.0
        return f.clock_s

    def _reset_lap(self, f, now, partial, fresh=True, after_event=False):
        """TUR BASLANGICI: yeni, bos bir tur durumu olusturur (onceki turdan hicbir sey tasinmaz).
        partial=None: turun basini gorup gormedigimize gore otomatik (tur saati < 2 sn ve ilk sektordeyse
        basini gormusuz sayilir).
        fresh=False: oyun tur sayacini artirdi ama tur saati henuz sifirlanmadi (eski turun degerini gosteriyor);
        bu durumda tur saatine dayanan degerler (baslangic saati) tur saati toparlaninca yenilenir."""
        cur = f.lap_current_ms
        if partial is None:
            partial = not (cur is not None and cur < 2000 and f.sector_index in (0, None))
        use_cur = fresh or not after_event
        self.lap = {
            "prev_count": f.lap_count, "partial": partial, "invalid": False, "pit": False,
            "suspect": False, "had_validity": False,
            "event_clock": self._lap_start_clock(f) if use_cur else None,
            "last_idx": f.sector_index, "s": [None, None], "pend_sector": None, "broken": False,
            "prev_last_ms": f.lap_last_ms, "prev_sector_x": f.last_sector_ms,
            "born": now, "seen_t": now,
            "cur_ms": cur if use_cur else None, "cur_t": now,
            "pre_rewind": None, "rewind_t": None,
            "live_s": (cur / 1000.0) if (use_cur and cur is not None and 0 <= cur <= MAX_LAP_MS) else 0.0,
            "overlong": False,
        }
        self._latch(f)

    def _latch(self, f):
        L = self.lap
        if f.lap_valid is not None:
            L["had_validity"] = True
            if f.lap_valid is False:
                L["invalid"] = True
        if f.in_pit:
            L["pit"] = True
        if f.lap_suspect:
            L["suspect"] = True

    def _laps(self, f, now):
        if self.pend:
            self._try_finalize(f, now)
        c = f.lap_count
        if c is None:
            self.lap_tracking = False
            self.lap = None
            return
        self.lap_tracking = True
        L = self.lap
        if L is None:
            self._reset_lap(f, now, partial=None)
            return
        pc = L["prev_count"]
        if c < pc or c > pc + 1:                 # SIFIRLAMA: oyun oturumu sifirlandi / tur kacirildi: yeniden esle
            self.pend = None
            if self.sess and L is not None and (c < pc):
                self.last_event = "Tur sayacı sıfırlandı: yarım kalan tur kaydedilmedi"
            self._reset_lap(f, now, partial=None)
            return
        if c == pc + 1:                          # TAMAMLANMA
            cb = L["pre_rewind"][0] if L["pre_rewind"] else L["cur_ms"]
            cur = f.lap_current_ms
            fresh = cur is None or cur < 2000 or (cb is not None and cur < cb - REWIND_TOL_MS)
            self._lap_event(f, now, fresh)
            self._reset_lap(f, now, partial=False, fresh=fresh, after_event=True)
            return
        if not self._timer(f, now):              # tur saati geri sardi: tur yeniden basladi
            return
        self._latch(f)
        self._sectors(f, now)
        L["prev_last_ms"] = f.lap_last_ms

    def _timer(self, f, now):
        """Tur saatini izler. False donerse tur sifirlanip yeniden baslatilmistir."""
        L = self.lap
        dt = now - L["seen_t"]
        L["seen_t"] = now
        if 0 < dt <= 1.0:
            L["live_s"] += dt
        if L["live_s"] > MAX_LAP_S and not L["overlong"]:
            L["overlong"] = True                 # tur sayaci sifirlanmiyor: sure sinirsiz buyur
            self.last_event = "Tur sayacı sıfırlanmıyor: bu tur kaydedilmeyecek"
        cur = f.lap_current_ms
        if cur is None:
            return True
        prev = L["cur_ms"]
        if prev is not None and cur < prev - REWIND_TOL_MS:
            if now - L["born"] < BIRTH_GRACE_S:
                # tur sayaci tur saatinden once artmisti: saat simdi sifirlandi, baslangic saatini yenile
                L["event_clock"] = self._lap_start_clock(f)
                L["live_s"] = cur / 1000.0
                L["overlong"] = False
            elif L["pre_rewind"] is None:
                L["pre_rewind"] = (prev, L["cur_t"])
                L["rewind_t"] = now
        L["cur_ms"], L["cur_t"] = cur, now
        if L["pre_rewind"] is not None and now - L["rewind_t"] > REWIND_GRACE_S:
            # SIFIRLAMA: tur sayaci artmadan tur saati basa dondu (pite donus / tur yeniden baslatma)
            self.last_event = "Tur sıfırlandı: yarım kalan tur kaydedilmedi"
            self._reset_lap(f, now, partial=None)
            return False
        return True

    def _lap_event(self, f, now, fresh=True):
        L = self.lap
        if L["pre_rewind"]:
            cur_before, cur_t = L["pre_rewind"]
        else:
            cur_before, cur_t = L["cur_ms"], L["cur_t"]
        clock_now = self._lap_start_clock(f) if fresh else f.clock_s
        self.sess["laps_completed"] += 1
        self.pend = {
            "t0": now, "prev_last": L["prev_last_ms"], "clock_now": clock_now,
            "clock_prev": L["event_clock"],
            "cur_before": cur_before, "cur_gap_s": max(0.0, now - cur_t) if cur_before is not None else None,
            "overlong": L["overlong"],
            "partial": L["partial"], "invalid": L["invalid"], "pit": L["pit"], "suspect": L["suspect"],
            "had_validity": L["had_validity"], "s": list(L["s"]), "broken": L["broken"],
            "ctx": self.ctx, "sess": self.sess,
        }
        self._try_finalize(f, now)

    def _try_finalize(self, f, now):
        p = self.pend
        if f.lap_last_ms is not None and f.lap_last_ms != p["prev_last"]:
            self._finalize(p, f.lap_last_ms, f.last_lap_sectors)
        elif now - p["t0"] > PEND_TIMEOUT:
            self._finalize(p, None, None)

    def _finalize(self, p, lap_ms, game_sectors):
        self.pend = None
        sess = p["sess"]
        if sess is not self.sess:        # baglam bu arada degisti
            return
        reason = None
        cb = p["cur_before"]
        if p["partial"]:
            reason = "yarım tur (PitApex tur ortasında başladı)"
        elif lap_ms is None or not (MIN_LAP_MS <= lap_ms <= MAX_LAP_MS):
            reason = "tur süresi oyundan okunamadı"
        elif p["overlong"]:
            reason = "tur süresi aşırı uzun (tur sayacı sıfırlanmadı)"
        elif cb is not None and (lap_ms < cb - 300 or
                                 lap_ms - cb > CUR_TOL_MS + 1000 * (p["cur_gap_s"] or 0.0)):
            reason = "tur süresi tur saatiyle doğrulanamadı"
        elif p["clock_now"] is not None and p["clock_prev"] is not None and \
                abs((p["clock_now"] - p["clock_prev"]) * 1000 - lap_ms) > CLOCK_TOL_MS:
            reason = "tur süresi oyun saatiyle doğrulanamadı"
        elif p["pit"]:
            reason = "pit yolu kullanıldı"
        elif p["invalid"]:
            reason = "oyun turu geçersiz saydı"
        elif p["suspect"]:
            reason = "tur şüpheli (pist dışı)"
        if not p["partial"]:
            sess.setdefault("lap_history", []).append({
                "number": sess["laps_completed"], "lap_ms": lap_ms,
                "valid": reason is None, "reason": reason or "",
                "verified": bool(p["had_validity"]), "sectors_ms": list(game_sectors) if game_sectors else None,
            })
        if reason:
            self.last_event = "Tur kaydedilmedi: " + reason
            self._persist()
            return

        sectors = None
        if game_sectors and abs(sum(game_sectors) - lap_ms) <= 2 and min(game_sectors) >= MIN_SECTOR_MS:
            sectors = tuple(game_sectors)
        elif not p["broken"] and p["s"][0] and p["s"][1]:
            s3 = lap_ms - p["s"][0] - p["s"][1]
            cand = (p["s"][0], p["s"][1], s3)
            if min(cand) >= MIN_SECTOR_MS:
                sectors = cand

        previous_lap_ms = sess["lap_times_ms"][-1] if sess["lap_times_ms"] else None
        if sess.get("lap_history"):
            sess["lap_history"][-1]["delta_previous_ms"] = lap_ms - previous_lap_ms if previous_lap_ms is not None else None
        sess["valid_laps"] += 1
        sess["lap_times_ms"].append(lap_ms)
        if sess["best_lap_ms"] is None or lap_ms < sess["best_lap_ms"]:
            sess["best_lap_ms"] = lap_ms
        if sectors:
            for i in range(3):
                b = sess["best_sectors_ms"][i]
                if b is None or sectors[i] < b:
                    sess["best_sectors_ms"][i] = sectors[i]
        game_id, track_id, car_id = p["ctx"]
        res = self.records.submit(game_id, self.game_names.get(game_id, game_id), track_id, sess["track_name"],
                                  car_id, sess["car_name"], lap_ms, sectors, verified=p["had_validity"])
        if res in ("first", "improved"):
            self.last_event = "Yeni rekor: %s" % fmt_ms(lap_ms)
        elif res == "write_error":
            self.last_event = "Tur tamamlandı; rekor diske yazılamadı"
        else:
            self.last_event = "Tur: %s" % fmt_ms(lap_ms)
        self._persist()

    # ---------------- sektor takibi ----------------
    def _sectors(self, f, now):
        L = self.lap
        idx = f.sector_index
        if idx is None:
            L["last_idx"] = None
            L["pend_sector"] = None
            return
        if L["pend_sector"]:
            self._resolve_sector(f, now)
        if L["last_idx"] is None:
            L["last_idx"] = idx
        elif idx != L["last_idx"]:
            if idx == 0 and L["last_idx"] == 2 and L["s"] == [None, None] and now - L["born"] < BIRTH_GRACE_S:
                pass        # oyun sektor gostergesini onceki turdan geriden guncelledi: sektor takibi bozulmaz
            elif idx == L["last_idx"] + 1 and idx in (1, 2):
                L["pend_sector"] = {"k": L["last_idx"], "x0": L["prev_sector_x"],
                                    "T0": f.lap_current_ms, "t0": now}
                self._resolve_sector(f, now)
            else:
                L["broken"] = True
                L["pend_sector"] = None
            L["last_idx"] = idx
        L["prev_sector_x"] = f.last_sector_ms

    def _resolve_sector(self, f, now):
        L = self.lap
        ps = L["pend_sector"]
        x, T = f.last_sector_ms, f.lap_current_ms
        lo, hi = SECTOR_WINDOW
        if x is not None and T is not None and x != ps["x0"]:
            if ps["k"] == 0:
                if lo <= T - x <= hi:
                    L["s"][0] = x
                    L["pend_sector"] = None
                    return
            else:
                s1 = L["s"][0]
                if s1 is not None and s1 > 5000 and x != s1:
                    cum = x > s1 and lo <= T - x <= hi            # oyun S1+S2 verdiyse
                    sep = lo <= T - (x + s1) <= hi                # oyun yalniz S2 verdiyse
                    if cum != sep:
                        L["s"][1] = (x - s1) if cum else x
                        L["pend_sector"] = None
                        return
        gave_up = (T is not None and ps["T0"] is not None and T - ps["T0"] > hi + 1300) or now - ps["t0"] > 2.0
        if gave_up:
            L["pend_sector"] = None

    # ---------------- arayuz ----------------
    def snapshot(self):
        with self.lock:
            if not self.sess:
                return {"has_session": False, "live": self.live, "lap_tracking": self.lap_tracking,
                        "last_event": self.last_event, "ended": False, "last_state": None}
            if not self.ended:
                self._summary()
            s = self.sess
            rec = self.records.get(s["game_id"], s["track_id"], s["car_id"])
            return {
                "has_session": True, "live": self.live, "lap_tracking": self.lap_tracking,
                "ended": self.ended, "ended_at": s.get("ended_at") or s.get("updated"),
                "last_state": dict(self.last_state) if self.last_state else None,
                "game_id": s["game_id"], "game_name": s.get("game_name", s["game_id"]),
                "track_name": s.get("track_name"), "car_name": s.get("car_name"),
                "started": s.get("started"),
                "laps_completed": s.get("laps_completed", 0), "valid_laps": s.get("valid_laps", 0),
                "lap_times_ms": list(s.get("lap_times_ms", [])),
                "avg_lap_ms": s.get("avg_lap_ms"), "best_lap_ms": s.get("best_lap_ms"),
                "best_sectors_ms": list(s.get("best_sectors_ms") or [None, None, None]),
                "theoretical_best_ms": s.get("theoretical_best_ms"),
                "avg_speed_kmh": s.get("avg_speed_kmh"), "max_speed_kmh": s.get("max_speed_kmh"),
                "max_rpm": s.get("max_rpm"), "throttle_avg_pct": s.get("throttle_avg_pct"),
                "brake_avg_pct": s.get("brake_avg_pct"), "record": rec, "prev_session": self.prev_session,
                "last_event": self.last_event,
            }
