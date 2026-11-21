"""Hiza bagli fan kontrolu. Pedal motorundan BAGIMSIZ kendi ipliginde calisir; pedal efektleri
kapali olsa bile fan calisir. Hiz bilgisini yalnizca pedal motorunun okuma sonucundan (engine.snap)
SALT-OKUNUR alir; Arduino'ya ortak ArduinoLink uzerinden yazar.

IKI FAN YUVASI: her fan kendi cikisina (M1..M4), kendi acik/kapali ayarina ve kendi hiz egrisine sahiptir.
 * Arduino kodu v4+: 'F<cikis 1-4>,<0-255>'  (ornek F3,128)
 * Arduino kodu v3 (eski): tek fan, cikis kodda sabit -> 'F,<0-255>' yalniz Fan 1 icin; Fan 2 icin v4 gerekir."""
import threading
import time


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


FAN_COUNT = 2
DEFAULT_OUTPUTS = (3, 4)          # Fan 1 -> M3, Fan 2 -> M4 (varsayilan; kullanici degistirir)


def normalized(cfg, default_output=3):
    """Tek fanin ayarlarini guvenli araliklara getirir (kutuya yazarken gecici bozuk deger olabilir).
    output: 0 = secilmedi, 1..4 = M1..M4."""
    def g(k, default):
        try:
            return float(cfg.get(k, default))
        except (TypeError, ValueError):
            return float(default)
    max_speed = clamp(g("max_speed", 300), 50, 600)
    try:
        output = int(cfg.get("output", default_output))
    except (TypeError, ValueError):
        output = default_output
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "output": output if 0 <= output <= 4 else default_output,
        "idle_pct": clamp(g("idle_pct", 25), 0, 100),
        "mid_speed": clamp(g("mid_speed", 150), 1, max_speed - 1),
        "mid_pct": clamp(g("mid_pct", 50), 0, 100),
        "max_speed": max_speed,
        "max_pct": clamp(g("max_pct", 100), 10, 100),
        "min_pwm": clamp(g("min_pwm", 60), 0, 200),
        "kick_ms": clamp(g("kick_ms", 400), 0, 2000),
        "ramp_up": clamp(g("ramp_up", 60), 5, 1000),
        "ramp_down": clamp(g("ramp_down", 30), 5, 1000),
        "no_data": "idle" if cfg.get("no_data") == "idle" else "stop",
    }


def curve_pct(speed_kmh, cfg):
    """Hiz -> fan gucu (%): 0 km/h = rolanti, orta nokta, maks hiz = %100; aralarinda dogrusal.
    Sonuc 'max_pct' guc sinirini asamaz."""
    c = normalized(cfg)
    pts = [(0.0, c["idle_pct"]), (c["mid_speed"], c["mid_pct"]), (c["max_speed"], 100.0)]
    s = max(0.0, speed_kmh)
    if s >= pts[-1][0]:
        pct = pts[-1][1]
    else:
        pct = pts[0][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if s <= x1:
                pct = y0 + (y1 - y0) * (s - x0) / (x1 - x0)
                break
    return min(pct, c["max_pct"])


def pct_to_pwm(pct, cfg):
    """% -> 0-255 PWM. 0 = durur; >0 ise fanin donmeye basladigi min_pwm'den baslar."""
    if pct <= 0.5:
        return 0
    c = normalized(cfg)
    pwm = c["min_pwm"] + (255 - c["min_pwm"]) * min(100.0, pct) / 100.0
    return int(clamp(round(pwm), 1, 255))


def default_fans():
    return [normalized({}, DEFAULT_OUTPUTS[i]) for i in range(FAN_COUNT)]


_LEGACY_KEYS = ("enabled", "idle_pct", "mid_speed", "mid_pct", "max_speed", "max_pct", "min_pwm", "kick_ms",
                "ramp_up", "ramp_down", "no_data")


def normalize_fans(raw):
    """Kayitli fan ayarini IKI fanlik listeye cevirir.
    * Yeni bicim: {"fans": [fan1, fan2]}
    * Eski bicim (tek fan, duz sozluk): Fan 1 = eski ayar (cikis M3), Fan 2 = varsayilan (kapali)."""
    # Eski dosya + varsayilan birlesince hem duz anahtarlar hem varsayilan "fans" bulunur: duz anahtarlar ESKI
    # kullanici ayaridir (yeni kayit duz anahtar yazmaz), bu yuzden once onlara bakilir.
    if isinstance(raw, dict) and any(k in raw for k in _LEGACY_KEYS):
        fans = default_fans()
        fans[0] = normalized(raw, DEFAULT_OUTPUTS[0])
        return fans
    if isinstance(raw, dict) and isinstance(raw.get("fans"), list):
        lst = raw["fans"]
        return [normalized(lst[i] if i < len(lst) and isinstance(lst[i], dict) else {}, DEFAULT_OUTPUTS[i])
                for i in range(FAN_COUNT)]
    return default_fans()


class FanChannel:
    """Tek fan yuvasinin durum makinesi (yumusatma, kalkis darbesi, test, durum metni). Iplik FanController'dadir."""
    KEEPALIVE = 0.5

    def __init__(self, ctl, index):
        self.ctl, self.index = ctl, index
        self.cur_pct = 0.0
        self.last_pwm_sent = None
        self.last_send = 0.0
        self.kick_until = 0.0
        self.out_pwm = 0
        self.test = None                       # (pct, bitis_zamani)
        self.sent_output = None                # son komutun gittigi cikis (cikis degisirse eskisi sifirlanir)
        self.status = {"text": "Kapalı", "level": "off", "speed": None, "pct": 0.0, "pwm": 0}
        self._t = time.monotonic()

    @property
    def link(self):
        return self.ctl.link

    def start_test(self, pct, seconds=5.0):
        self.test = (float(pct), time.monotonic() + seconds)

    def stop_test(self):
        self.test = None

    def line(self, output, pwm):
        """Komut metni: v4+ 'F<cikis>,<pwm>'; v3'te eski 'F,<pwm>' (yalniz Fan 1)."""
        if getattr(self.link, "multi_output", False):
            return "F%d,%d" % (output, pwm)
        return "F,%d" % pwm

    def blocked(self, cfg, other_cfg):
        """(metin, seviye) ya da None: bu fan calistirilamaz."""
        link = self.link
        multi = getattr(link, "multi_output", False)
        if cfg["output"] == 0:
            return "Çıkış seçilmedi (M1-M4'ten birini seç)", "off"
        if self.index > 0 and cfg["enabled"] and link.fw_version is not None and link.fan_supported and not multi:
            return ("İkinci fan için Arduino kodu v4 gerekli (şu an v%s). firmware/PedalHaptic.ino dosyasını yeniden yükle."
                    % link.fw_version), "bad"
        if self.index > 0 and cfg["enabled"] and other_cfg["enabled"] and other_cfg["output"] == cfg["output"]:
            return "Aynı çıkış Fan 1'de de seçili: farklı bir çıkış seç", "bad"
        return None

    # --- hedef ve durum ---
    def decide(self, cfg, now):
        """(hedef_yuzde, durum_metni, seviye, hiz). Hiz yoksa None."""
        link = self.link
        if not link.connected:
            return 0.0, "Arduino bağlı değil", "warn", None
        if not link.ready:
            return 0.0, "Arduino hazırlanıyor…", "warn", None
        if link.fw_version is None:
            return 0.0, "Arduino kod sürümü bekleniyor…", "warn", None
        if not link.fan_supported:
            return 0.0, "Arduino kodu eski (v%s). Fan için firmware/PedalHaptic.ino dosyasını yeniden yükleyin." \
                % link.fw_version, "bad", None
        if self.test and now < self.test[1]:
            return self.test[0], "Test: %%%.0f" % self.test[0], "ok", None
        self.test = None
        if not cfg["enabled"]:
            return 0.0, "Kapalı", "off", None
        snap = self.ctl.engine.snap or {}
        t = snap.get("t")
        speed = None
        if snap.get("live") and t and snap.get("valid", True):
            sp = t.get("speed")
            if isinstance(sp, (int, float)) and 0 <= sp < 700:
                speed = float(sp)
        if speed is None:
            if cfg["no_data"] == "idle":
                return cfg["idle_pct"], "Telemetri yok: fan rölantide", "warn", None
            return 0.0, "Telemetri yok: fan durduruldu", "warn", None
        pct = curve_pct(speed, cfg)
        return pct, "Aktif: %.0f km/h → %%%.0f" % (speed, pct), "ok", speed

    def tick(self, now, cfg, other_cfg, conflict=None):
        dt = max(0.0, min(0.5, now - self._t))
        self._t = now
        out_n = cfg["output"]
        block = self.blocked(cfg, other_cfg)
        # cikis degistiyse / fan secimi kalktiysa ESKI cikisi sifirla (fan donmeye devam etmesin)
        if self.sent_output is not None and self.sent_output != out_n and getattr(self.link, "multi_output", False) \
                and self.link.ready:
            self.link.write_line("F%d,0" % self.sent_output)
            self.sent_output = None
            self.last_pwm_sent = None
        if block is not None:
            text, level = block
            target, speed = 0.0, None
        else:
            target, text, level, speed = self.decide(cfg, now)
            if conflict:
                text, level = "⚠ %s. %s" % (conflict, text), "warn" if level in ("ok", "off") else level

        # yumusatma: ani siçrama olmasin
        if target > self.cur_pct:
            self.cur_pct = min(target, self.cur_pct + cfg["ramp_up"] * dt)
        else:
            self.cur_pct = max(target, self.cur_pct - cfg["ramp_down"] * dt)
        if target == 0.0 and self.cur_pct < 1.0:
            self.cur_pct = 0.0

        pwm = pct_to_pwm(self.cur_pct, cfg)
        # kick-start: duruştan kalkarken kisa sure tam guc (cogu fan dusuk PWM'de kendi baslayamaz)
        if pwm > 0 and self.out_pwm == 0 and cfg["kick_ms"] > 0 and pwm < 255:
            self.kick_until = now + cfg["kick_ms"] / 1000.0
        out = 255 if (pwm > 0 and now < self.kick_until) else pwm
        self.out_pwm = out

        multi = getattr(self.link, "multi_output", False)
        # v3'te komut 'F,<hiz>' tek (sabit) fana gider: Fan 2 ASLA gondermemeli (Fan 1'i sifirlardi)
        can_send = block is None and self.link.ready and self.link.fan_supported and (multi or self.index == 0)
        if can_send:
            if out != self.last_pwm_sent or now - self.last_send > self.KEEPALIVE:
                if self.link.write_line(self.line(out_n, out)):
                    self.last_pwm_sent = out
                    self.last_send = now
                    self.sent_output = out_n
        else:
            self.last_pwm_sent = None
            self.cur_pct = 0.0
            self.out_pwm = 0
        self.status = {"text": text, "level": level, "speed": speed, "pct": self.cur_pct, "pwm": self.out_pwm}


class FanController(threading.Thread):
    """Iki fan yuvasini tek iplikte yonetir. Eski API korunur: status/start_test/stop_test Fan 1'e bakar."""

    def __init__(self, link, engine, cfg_getter):
        super().__init__(daemon=True)
        self.link = link
        self.engine = engine
        self.cfg_getter = cfg_getter
        self.running = True
        self.channels = [FanChannel(self, i) for i in range(FAN_COUNT)]

    # --- eski (tek fan) API: Fan 1 ---
    @property
    def status(self):
        return self.channels[0].status

    @status.setter
    def status(self, value):
        self.channels[0].status = value

    @property
    def statuses(self):
        return [c.status for c in self.channels]

    @property
    def test(self):
        return self.channels[0].test

    def start_test(self, pct, seconds=5.0, index=0):
        self.channels[index].start_test(pct, seconds)

    def stop_test(self, index=None):
        for i, c in enumerate(self.channels):
            if index is None or i == index:
                c.stop_test()

    def conflicts_for(self, fans):
        """{fan_indeksi: metin}: fan cikisi bir pedal efektiyle de kullaniliyorsa uyari."""
        pedal_cfg = getattr(self.engine, "cfg", None)
        if not isinstance(pedal_cfg, dict):
            return {}
        from core.outputs import conflicts
        out = {}
        for n, kind, text in conflicts(pedal_cfg, fans):
            if kind != "pedal+fan":
                continue
            for i, f in enumerate(fans):
                if f["enabled"] and f["output"] == n:
                    out[i] = text
        return out

    def tick(self, now):
        fans = normalize_fans(self.cfg_getter() or {})
        warn = self.conflicts_for(fans)
        for i, ch in enumerate(self.channels):
            ch.tick(now, fans[i], fans[1 - i], warn.get(i))

    def run(self):
        while self.running:
            try:
                self.tick(time.monotonic())
            except Exception as e:      # fan hatasi hicbir seyi durdurmasin
                for c in self.channels:
                    c.status = {"text": "Fan hatası: %s" % e, "level": "bad", "speed": None, "pct": 0, "pwm": 0}
            time.sleep(0.05)
        try:
            if getattr(self.link, "multi_output", False):
                for n in range(1, 5):
                    self.link.write_line("F%d,0" % n)
            self.link.write_line("F,0")
        except Exception:
            pass
