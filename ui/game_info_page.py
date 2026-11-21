"""03 - Oyun Bilgileri. Her satir uc turden biridir:
  ● canli      : oyundan su an okunan / bu oturumda hesaplanan deger
  ◆ kayitli    : gecmisten (kayit dosyasindan) gelen deger
  Veri alinamiyor : oyun bu degeri vermiyor veya okunan deger guvenilir degil (asla tahmin edilmez)"""
import time
from types import SimpleNamespace
from tkinter import ttk

from core.models import fmt_hms, fmt_ms, gear_text

NA = "Veri alınamıyor"
KPA_TO_PSI = 1 / 6.894757


# ---------------- bicimlendirme (None -> None; yani 'veri yok') ----------------
def f_speed(v):
    return None if v is None else "%.0f km/h" % v


def f_pct01(v):
    return None if v is None else "%%%.0f" % (v * 100)


def f_pct(v):
    return None if v is None else "%%%.0f" % v


def f_rpm(v):
    return None if v is None else "%.0f" % v


def f_temp(v):
    return None if v is None else "%.0f °C" % v


def f_fuel(v):
    return None if v is None else "%.1f L" % v


def f_wheels(vals, conv, fmt):
    if not vals:
        return None
    short = ("SÖ", "SaÖ", "SoA", "SaA")
    parts = []
    for n, v in zip(short, vals):
        parts.append("%s %s" % (n, fmt % conv(v) if v is not None else "—"))
    return "   ".join(parts)


def f_level(active, level):
    parts = []
    if active is not None:
        parts.append("aktivite %%%.0f" % (active * 100))
    if level is not None:
        parts.append("ayar %.0f" % level)
    return " · ".join(parts) if parts else None


def f_sectors(secs):
    if not secs or all(s is None for s in secs):
        return None
    return "  |  ".join("S%d %s" % (i + 1, fmt_ms(s) if s is not None else "—") for i, s in enumerate(secs))


def f_prev(sess):
    if not sess:
        return None
    best = fmt_ms(sess.get("best_lap_ms")) if sess.get("best_lap_ms") else "—"
    return "%s · %s tur · en iyi %s" % (sess.get("started", "?")[:16], sess.get("laps_completed", 0), best)


def f_engine(v):
    return None if v is None else ("Çalışıyor" if v else "Kapalı")


class InfoRow:
    def __init__(self, parent, row, label):
        self.dot = ttk.Label(parent, text="", width=2)
        self.name = ttk.Label(parent, text=label, style="Muted.TLabel")
        self.val = ttk.Label(parent, text=NA, style="NA.TLabel")
        self.dot.grid(row=row, column=0, sticky="w", padx=(6, 0), pady=1)
        self.name.grid(row=row, column=1, sticky="w", padx=4, pady=1)
        self.val.grid(row=row, column=2, sticky="w", padx=(4, 8), pady=1)

    def set(self, text, kind="live"):
        """kind: 'live' | 'saved'. text None/'' -> Veri alinamiyor."""
        if text is None or text == "":
            self.dot.config(text="", style="TLabel")
            self.val.config(text=NA, style="NA.TLabel")
        elif kind == "saved":
            self.dot.config(text="◆", style="SavedDot.TLabel")
            self.val.config(text=text, style="Saved.TLabel")
        else:
            self.dot.config(text="●", style="LiveDot.TLabel")
            self.val.config(text=text, style="Live.TLabel")


class GameInfoPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.rows = {}
        self.build()

    def card(self, col, title):
        f = ttk.LabelFrame(self, text=title)
        f.grid(row=1, column=col, sticky="nsew", padx=6, pady=4)
        f.columnconfigure(2, weight=1)
        self.columnconfigure(col, weight=1, uniform="cards")
        return f

    def add(self, card, key, label):
        self.rows[key] = InfoRow(card, card.grid_size()[1], label)

    def section(self, card, text):
        r = card.grid_size()[1]
        ttk.Label(card, text=text, style="Big.TLabel").grid(row=r, column=0, columnspan=3, sticky="w",
                                                             padx=6, pady=(8, 2))

    def build(self):
        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=6, pady=(4, 0))
        self.game_lbl = ttk.Label(top, text="Oyun algılanmadı", style="Big.TLabel")
        self.game_lbl.pack(side="left")
        self.status_lbl = ttk.Label(top, text="", style="Muted.TLabel")
        self.status_lbl.pack(side="left", padx=12)

        a = self.card(0, "A · Oturum ve tur istatistikleri")
        self.add(a, "time", "Oyun süresi")
        self.add(a, "track", "Aktif pist")
        self.add(a, "best", "Oturum en hızlı tur")
        self.add(a, "sect", "Oturum en iyi sektörler")
        self.add(a, "avg", "Ortalama tur (geçerli)")
        self.add(a, "laps", "Tamamlanan tur")
        self.add(a, "theo", "Teorik en iyi tur")
        self.section(a, "Geçmiş kayıtlar")
        self.add(a, "rec", "Rekor (pist + araç)")
        self.add(a, "recs", "Rekor sektörleri")
        self.add(a, "prev", "Önceki oturum")
        self.note_a = ttk.Label(a, text="", style="Warn.TLabel", wraplength=330, justify="left")
        self.note_a.grid(row=a.grid_size()[1], column=0, columnspan=3, sticky="w", padx=6, pady=(6, 4))

        b = self.card(1, "B · Sürüş performansı")
        self.section(b, "Anlık")
        self.add(b, "speed", "Hız")
        self.add(b, "thr", "Gaz (anlık)")
        self.add(b, "brk", "Fren (anlık)")
        self.add(b, "rpm", "Devir (anlık)")
        self.add(b, "abs", "ABS")
        self.add(b, "tc", "TC")
        self.section(b, "Oturum (hareket halindeyken)")
        self.add(b, "avgspd", "Ortalama hız")
        self.add(b, "maxspd", "Maksimum hız")
        self.add(b, "maxrpm", "En yüksek devir")
        self.add(b, "thravg", "Gaz (oturum ort.)")
        self.add(b, "brkavg", "Fren (oturum ort.)")

        c = self.card(2, "C · Araç ve yarış durumu")
        self.add(c, "car", "Araç modeli")
        self.add(c, "fuel", "Yakıt")
        self.add(c, "ttemp", "Lastik sıcaklığı")
        self.add(c, "tpress", "Lastik basıncı")
        self.add(c, "water", "Motor suyu")
        self.add(c, "oil", "Motor yağı")
        self.add(c, "gear", "Vites")
        self.add(c, "engine", "Motor durumu")
        ttk.Label(c, text="Lastik sırası: SÖ sol ön, SaÖ sağ ön, SoA sol arka, SaA sağ arka.",
                  style="Muted.TLabel", wraplength=330, justify="left").grid(
            row=c.grid_size()[1], column=0, columnspan=3, sticky="w", padx=6, pady=(8, 2))

        leg = ttk.Frame(self)
        leg.grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))
        ttk.Label(leg, text="●", style="LiveDot.TLabel").pack(side="left")
        ttk.Label(leg, text=" canlı telemetri / bu oturumdan hesaplanan     ", style="Muted.TLabel").pack(side="left")
        ttk.Label(leg, text="◆", style="SavedDot.TLabel").pack(side="left")
        ttk.Label(leg, text=" kayıtlı geçmiş     ", style="Muted.TLabel").pack(side="left")
        ttk.Label(leg, text="Veri alınamıyor: oyun bu bilgiyi vermiyor ya da okunan değer güvenilir değil "
                            "(tahmin gösterilmez).", style="Muted.TLabel").pack(side="left")

    # ---------------- guncelleme ----------------
    def tick(self, visible):
        """Oyun kapansa / veri kesilse bile son oturumun verileri ekranda KALIR (◆ kayitli olarak).
        Veri ancak kullanici verileri temizlerse ya da yeni oturum baslayinca degisir."""
        if not visible:
            return
        st = self.app.telemetry.state()
        snap = self.app.tracker.snapshot()
        f = st["frame"]
        live = bool(f and f.live)
        has = bool(snap.get("has_session"))
        ls = snap.get("last_state") if has else None
        # canli degilken son alinan kareyi (kayitli) goster
        src = f if live else (SimpleNamespace(**ls) if ls else None)
        kind = "live" if live else "saved"
        R = self.rows

        gname = st["game_name"] or (snap.get("game_name") if has else None)
        if gname and not st["running"] and has:
            gname += "  (son oturum)"
        self.game_lbl.config(text=gname or "Oyun algılanmadı")
        self.status_lbl.config(text=st["status"])

        # --- oyun suresi ---
        el = st["elapsed_s"]
        if st["running"] and el is not None:
            R["time"].set(fmt_hms(el), "live")
        elif el is not None:
            R["time"].set(fmt_hms(el) + "  (oyun kapandı)", "saved")
        else:
            R["time"].set(None)

        # --- pist / arac ---
        trk = (f.track_name if f and f.track_name else None) or (snap.get("track_name") if has else None)
        car = (f.car_name if f and f.car_name else None) or (snap.get("car_name") if has else None)
        R["track"].set(trk, "live" if (f and f.track_name and live) else "saved")
        R["car"].set(car, "live" if (f and f.car_name and live) else "saved")

        # --- A: oturum ve tur ---
        if has:
            R["best"].set(fmt_ms(snap["best_lap_ms"]) if snap["best_lap_ms"] else None, kind)
            R["sect"].set(f_sectors(snap["best_sectors_ms"]), kind)
            R["avg"].set(fmt_ms(snap["avg_lap_ms"]) if snap["avg_lap_ms"] else None, kind)
            R["laps"].set("%d  (geçerli: %d)" % (snap["laps_completed"], snap["valid_laps"]), kind)
            R["theo"].set(fmt_ms(snap["theoretical_best_ms"]) if snap["theoretical_best_ms"] else None, kind)
            rec = snap["record"]
            R["rec"].set(fmt_ms(rec["lap_ms"]) + ("" if rec.get("verified") else "  (doğrulanmamış)") if rec else None,
                         "saved")
            R["recs"].set(f_sectors([rec.get("s1_ms"), rec.get("s2_ms"), rec.get("s3_ms")]) if rec else None, "saved")
            R["prev"].set(f_prev(snap["prev_session"]), "saved")
        else:
            for k in ("best", "sect", "avg", "laps", "theo", "rec", "recs"):
                R[k].set(None)
            last = self.app.sessions.recent(1)
            R["prev"].set(f_prev(last[0]) if last else None, "saved")

        notes = []
        if has and not live:
            when = (ls or {}).get("t") or snap.get("ended_at") or "?"
            if not st["running"]:
                notes.append("Oyun kapalı: son oturumun verileri korunuyor (son veri %s). "
                             "Yeni oturum başlayınca bu oturum arşive geçer." % when)
            elif snap.get("ended"):
                notes.append("Yeni oturum bekleniyor: önceki oturumun verileri gösteriliyor (son veri %s)." % when)
            else:
                notes.append("Telemetri akmıyor: son alınan veriler korunuyor (son veri %s)." % when)
        elif live and not has:
            notes.append("Pist veya araç bilgisi okunamadı: oturum ve rekor takibi kapalı.")
        elif live and has and not snap["lap_tracking"]:
            notes.append("Bu oyundan tur bilgisi okunamıyor: tur takibi kapalı.")
        if f and f.notes and live:
            notes.extend(f.notes)
        if has and snap.get("last_event"):
            notes.append(snap["last_event"])
        self.note_a.config(text="\n".join(notes))

        # --- B: anlik (canli ya da son alinan kare) ---
        g = (lambda attr: getattr(src, attr, None) if src else None)
        R["speed"].set(f_speed(g("speed_kmh")), kind)
        R["thr"].set(f_pct01(g("throttle")), kind)
        R["brk"].set(f_pct01(g("brake")), kind)
        R["rpm"].set(f_rpm(g("rpm")), kind)
        R["abs"].set(f_level(g("abs_active"), g("abs_level")), kind)
        R["tc"].set(f_level(g("tc_active"), g("tc_level")), kind)
        # --- B: oturum ---
        if has:
            R["avgspd"].set(f_speed(snap["avg_speed_kmh"]), kind)
            R["maxspd"].set(f_speed(snap["max_speed_kmh"]), kind)
            R["maxrpm"].set(f_rpm(snap["max_rpm"]), kind)
            R["thravg"].set(f_pct(snap["throttle_avg_pct"]), kind)
            R["brkavg"].set(f_pct(snap["brake_avg_pct"]), kind)
        else:
            for k in ("avgspd", "maxspd", "maxrpm", "thravg", "brkavg"):
                R[k].set(None)

        # --- C ---
        R["fuel"].set(f_fuel(g("fuel_l")), kind)
        R["ttemp"].set(f_wheels(g("tyre_temp_c"), lambda v: v, "%.0f°"), kind)
        R["tpress"].set(f_wheels(g("tyre_press_kpa"), lambda v: v * KPA_TO_PSI, "%.1f psi"), kind)
        R["water"].set(f_temp(g("water_c")), kind)
        R["oil"].set(f_temp(g("oil_c")), kind)
        R["gear"].set(gear_text(g("gear")), kind)
        R["engine"].set(f_engine(g("engine_running")), kind)
