"""LED matris (MAX7219 8x8) kontrolcusu. Pedal/fan'dan BAGIMSIZ: kendi Arduino baglantisi ve kendi ipligi vardir.
Oyun verisini (vites) yalnizca pedal motorunun okumasindan (engine.snap) SALT-OKUNUR alir.

Arduino'ya komutlar: 'B,<0-15>' parlaklik, 'D,<16 hex>' goruntu (8 satir), 'C' temizle, 'V' -> 'LED<n>' cevabi.
Goruntu degisince hemen, degismese de KEEPALIVE araligiyla gonderilir; Arduino 3 sn komut gelmezse ekrani temizler."""
import threading
import time

from core import led_matrix as M


class LedController(threading.Thread):
    KEEPALIVE = 1.0
    ASK_EVERY = 1.0
    ID_TIMEOUT = 4.0          # baglandiktan sonra LED kodu bu sure icinde cevap vermezse uyar

    def __init__(self, link, engine, cfg_getter):
        super().__init__(daemon=True)
        self.link, self.engine, self.cfg_getter = link, engine, cfg_getter
        self.running = True
        self.test = None                      # (satirlar, bitis_zamani)
        self.last_hex = None
        self.last_bright = None
        self.last_send = 0.0
        self.last_ask = 0.0
        self.connected_at = None
        self._adjust_last = {}
        self._adjust_active = None
        self._adjust_source = None
        self.status = {"text": "Bağlı değil", "level": "off", "rows": M.BLANK, "info": "", "gear": None}

    # ---------- test ----------
    def start_test(self, rows, seconds=4.0):
        self.test = (tuple(rows), time.monotonic() + seconds)

    def stop_test(self):
        self.test = None

    # ---------- durum ----------
    def _blocked(self, now):
        """(metin, seviye) ya da None: kart komut almaya hazir degil."""
        L = self.link
        if not L.connected:
            self.connected_at = None
            return "LED kartı bağlı değil", "off"
        if self.connected_at is None:
            self.connected_at = now
        if not L.ready:
            return "LED kartı hazırlanıyor…", "warn"
        if not L.led_ok:
            if now - self.last_ask > self.ASK_EVERY:
                self.last_ask = now
                L.write_line("V")
            if L.fw_version is not None:
                return ("Bu port pedal/fan Arduino'su gibi görünüyor (kod v%s). LED kartının kendi portunu seç."
                        % L.fw_version), "bad"
            if now - self.connected_at > self.ID_TIMEOUT:
                return "LED kartı cevap vermiyor: firmware/LedMatrix/LedMatrix.ino yüklü mü, port doğru mu?", "bad"
            return "LED kartı bekleniyor…", "warn"
        return None

    def image(self, cfg, now):
        """(goruntu, bilgi metni, vites) - yon donusumu uygulanmadan."""
        if self.test and now < self.test[1]:
            return self.test[0], "Test görüntüsü", None
        self.test = None
        if not cfg["enabled"]:
            return M.BLANK, "Kapalı", None
        gear = M.live_gear(self.engine.snap, getattr(self.engine.src, "NAME", ""))
        flag, side = M.live_alerts(self.engine.snap)
        # Yeni oturumda önceki seviyelerden sahte değişiklik üretme.
        snap = self.engine.snap
        source = getattr(self.engine.src, "NAME", "")
        live = bool(snap and snap.get("live") and snap.get("valid", True))
        if not live or source != self._adjust_source:
            self._adjust_last = {}
            self._adjust_active = None
            self._adjust_source = source
        else:
            current = M.adjustment_values(snap)
            for key, value in current.items():
                if key in self._adjust_last and value != self._adjust_last[key] and cfg["adjustment_enabled"].get(key):
                    self._adjust_active = (key, value, now + cfg["adjustment_seconds"], "up" if value > self._adjust_last[key] else "down")
                self._adjust_last[key] = value
        if cfg["show_proximity"] and side:
            left = M.custom_image(cfg,"left",M.proximity_pattern("left")) if side in ("left","both") else M.BLANK
            right = M.custom_image(cfg,"right",M.proximity_pattern("right")) if side in ("right","both") else M.BLANK
            base = tuple(a | b for a,b in zip(left,right))
            if side == "rear": base = M.custom_image(cfg,"rear",M.proximity_pattern("rear"))
            if side == "both": base = M.custom_image(cfg,"both",base)
            rows = base if not cfg["blink_proximity"] or int(now * cfg["blink_proximity_speed"] * 2) % 2 == 0 else M.BLANK
            return rows, "Yan araç: " + side, gear
        if cfg["show_flags"] and flag and cfg["flag_enabled"].get(flag,False):
            base = M.custom_image(cfg,flag,M.FLAG_PATTERNS[flag])
            rows = base if not cfg["blink_flags"] or int(now * cfg["blink_flag_speed"] * 2) % 2 == 0 else M.BLANK
            return rows, "Bayrak: " + M.FLAG_NAMES[flag], gear
        if cfg["show_adjustments"] and self._adjust_active and now < self._adjust_active[2]:
            key, value, _, direction = self._adjust_active
            return M.custom_image(cfg, "adjust_%s_%d" % (key, int(round(value))), M.adjustment_image(key, value)), "Ayar: %s %s (%s)" % (M.ADJUSTMENTS[key], int(round(value)), direction), gear
        if cfg["show_gear"]:
            rows, info = M.feature_image(cfg, gear)
            return rows, info, gear
        return M.BLANK, "Etkin gösterge yok", gear

    def tick(self, now):
        cfg = M.normalized(self.cfg_getter() or {})
        rows, info, gear = self.image(cfg, now)
        block = self._blocked(now)
        if block is not None:
            text, level = block
            self.last_hex = self.last_bright = None             # yeniden baglaninca her sey tekrar gonderilsin
            self.status = {"text": text, "level": level, "rows": rows, "info": info, "gear": gear}
            return
        L = self.link
        if cfg["brightness"] != self.last_bright:
            if L.write_line("B,%d" % cfg["brightness"]):
                self.last_bright = cfg["brightness"]
        hx = M.to_hex(M.transform(rows, cfg["rotation"], cfg["flip_h"], cfg["flip_v"]))
        if hx != self.last_hex or now - self.last_send > self.KEEPALIVE:
            if L.write_line("D,%s" % hx):
                self.last_hex, self.last_send = hx, now
        self.status = {"text": "Bağlı: %s" % info if cfg["enabled"] or self.test else "Bağlı (LED aydınlatma kapalı)",
                       "level": "ok" if cfg["enabled"] or self.test else "off", "rows": rows, "info": info, "gear": gear}

    def run(self):
        while self.running:
            try:
                self.tick(time.monotonic())
            except Exception as e:           # LED hatasi hicbir seyi durdurmasin
                self.status = {"text": "LED hatası: %s" % e, "level": "bad", "rows": M.BLANK, "info": "", "gear": None}
            time.sleep(0.05)
        try:
            self.link.write_line("C")
        except Exception:
            pass
