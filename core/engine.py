"""Pedal titresim motoru. Efekt hesabi (compute/motor_pwm) ve ana dongu (run), PedalHaptic.py'deki
haliyle AYNEN tasindi. Degisen tek sey: seri port islemleri artik hardware/arduino.py'deki
ortak ArduinoLink uzerinden yapiliyor (fan da ayni porta yazabilsin diye)."""
import copy
import threading
import time

from telemetry.legacy_sources import ACCSource, SOURCES, probe_games

EFFECTS = {
    "abs":   {"name": "ABS"},
    "lock":  {"name": "Tekerlek kilitlenme"},
    "blim":  {"name": "Fren limiter (Brake Limiter)"},
    "tc":    {"name": "Traction Control (TC)"},
    "slip":  {"name": "Kayma"},
    "rev":   {"name": "Devir sınırı"},
    "shift": {"name": "Vites geçişi"},
    "gup":   {"name": "Vites yükseltme (Gear Up)"},
    "gdown": {"name": "Vites düşürme (Gear Down)"},
}

# Motor shield'in 4 cikisi: M1..M4 (indeks 0..3). Her efekt BIR VEYA BIRDEN COK cikisa atanabilir.
MOTOR_COUNT = 4
MOTOR_NAMES = ["M1", "M2", "M3", "M4"]
MOTOR_CHOICES = ["Fren motoru (M1)", "Gaz motoru (M2)", "Ikisi birden"]      # ESKI ayar dosyalarini okumak icin (motor: 0/1/2)
M3M4_FW_MIN = 4                                                             # M3/M4 titresim motoru icin gereken Arduino kodu surumu


def effect_motors(ck, key=None):
    """Efektin motor listesi (0 tabanli, tekrarsiz, sirali). Yeni ayar 'motors' listesidir.
    Eski ayar 'motor' (0=M1, 1=M2, 2=ikisi) varsa o kullanilir; ayar dosyalari bozulmaz.
    Gecersiz/bos sonuc: efektin varsayilan motoru."""
    default = list(DEFAULTS[key]["motors"]) if key in DEFAULTS else [0]
    if "motor" in ck:                                    # eski kayit (arayuz artik yazmaz)
        try:
            m = int(ck["motor"])
        except (TypeError, ValueError):
            return default
        return {0: [0], 1: [1], 2: [0, 1]}.get(m, default)
    raw = ck.get("motors")
    if not isinstance(raw, (list, tuple)):
        return default
    out = []
    for v in raw:
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        if 0 <= i < MOTOR_COUNT and i not in out:
            out.append(i)
    return sorted(out) if out else default

# Ortak yeni alanlar (eski efektlerin davranisini degistirmeyen varsayilanlar):
#   min_pct / max_pct : efektin kendi guc araligi (%). Varsayilan 0-100 = eski davranis.
#   sens              : hassasiyet (%). 50 = eski davranis. Efekte gore anlami UI'da yazar.
_X = {"min_pct": 0, "max_pct": 100, "sens": 50}
DEFAULTS = {
    "abs":   dict(enabled=True,  motors=[0], intensity=80, freq=12, duty=50, thr=0.01, hold=60, **_X),
    "lock":  dict(enabled=True,  motors=[0], intensity=90, freq=0,  duty=50, thr=0.25, hold=50, **_X),
    # Fren limiter: thr/full/hyst fren pedali YUZDESI (0-100). thr'de baslar, full'de tam guca ulasir.
    "blim":  dict(enabled=False, motors=[0], intensity=60, freq=15, duty=50, thr=80, full=100, hyst=5, hold=40,
                  min_pct=0, max_pct=100, sens=50),
    "tc":    dict(enabled=True,  motors=[1], intensity=70, freq=10, duty=50, thr=0.01, hold=60, **_X),
    "slip":  dict(enabled=True,  motors=[1], intensity=60, freq=0,  duty=50, thr=0.25, hold=50, **_X),
    "rev":   dict(enabled=False, motors=[1], intensity=70, freq=25, duty=50, thr=0.97, hold=40, **_X),
    "shift": dict(enabled=False, motors=[1], intensity=70, freq=0,  duty=50, thr=0.0,  hold=120, **_X),
    # Vites yukseltme / dusurme: hold = titresim suresi (ms), sens = tepki hassasiyeti (%, 100 = aninda)
    "gup":   dict(enabled=False, motors=[1], intensity=70, freq=0,  duty=50, thr=0.0,  hold=100, min_pct=0, max_pct=100, sens=80),
    "gdown": dict(enabled=False, motors=[1], intensity=60, freq=0,  duty=50, thr=0.0,  hold=100, min_pct=0, max_pct=100, sens=80),
}

GEAR_CONFIRM_MAX_S = 0.15        # tepki hassasiyeti %0 iken vitesin kararli kalmasi gereken sure

# Vites numarasi oyuna gore farkli: bu kaynaklarda 0=R, 1=N, 2=1. vites. Digerlerinde -1=R, 0=N, 1=1. vites.
_GEAR_OFFSET = {"ACC": 1, "AC": 1, "BeamNG": 1}


def norm_gear(source, g):
    """Normalize vites: -1=R, 0=N, 1..=ileri vites."""
    try:
        return int(g) - _GEAR_OFFSET.get(source, 0)
    except (TypeError, ValueError):
        return None


PWM_CHOICES = ["1 kHz (varsayilan)", "2 kHz", "8 kHz", "64 kHz (cok sessiz)"]
DEFAULT_MOTORS = {"pwm": 0, **{"min%d" % i: 0 for i in range(1, 5)}, **{"max%d" % i: 100 for i in range(1, 5)}}


class Engine(threading.Thread):
    def __init__(self, cfg, link):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.link = link
        self.src = ACCSource()
        self.pending_source = None
        self.auto = True
        self.mcfg = cfg.setdefault("_motors", dict(DEFAULT_MOTORS))
        self.pwm_sent = None
        self.last_probe = 0.0
        self.last_gear = None
        self.gear_det = {k: {"stable": None, "cand": None, "fwd": None} for k in ("gup", "gdown")}
        self.blim_on = False
        self.running = True
        self.snap = {}
        self.test = None
        self.state = {k: (0.0, 0.0) for k in EFFECTS}
        self.active = {k: False for k in EFFECTS}
        self.last_cmd = [(-1, -1, -1)] * MOTOR_COUNT
        self.last_send = [0.0] * MOTOR_COUNT
        self.last_pid = None
        self.last_change = time.perf_counter()
        self.hz = 0.0

    # --- seri port (ortak baglanti uzerinden) ---
    def connect(self, port):
        self.link.connect(port)
        self.last_cmd = [(-1, -1, -1)] * MOTOR_COUNT
        self.pwm_sent = None

    def disconnect(self):
        self.link.disconnect()

    def send(self, out, now):
        link = self.link
        ser = link.ser
        if not ser or time.time() < link.ready_at:
            return
        try:
            with link.lock:
                code = int(self.mcfg.get("pwm", 0))
                if self.pwm_sent != code:
                    ser.write(("Q%d\n" % code).encode())
                    self.pwm_sent = code
                n_out = MOTOR_COUNT if (link.fw_version or 0) >= M3M4_FW_MIN else 2     # eski kod yalniz M1/M2 bilir
                for m in range(n_out):
                    if out[m] != self.last_cmd[m] or now - self.last_send[m] > 0.05:
                        ser.write(("M%d,%d,%d,%d\n" % (m + 1, out[m][0], out[m][1], out[m][2])).encode())
                        self.last_cmd[m] = out[m]
                        self.last_send[m] = now
                link.service_locked(ser, now)
        except Exception as e:
            link.fail(e)

    # --- efekt hesabi ---
    def compute(self, t, now):
        c = self.cfg
        trig = {k: 0.0 for k in EFFECTS}
        if t:
            if t["abs"] > c["abs"]["thr"]:
                trig["abs"] = 1.0
            if t["tc"] > c["tc"]["thr"]:
                trig["tc"] = 1.0
            sr = t["slipRatio"]
            if t["brake"] > 0.1 and t["speed"] > 20:
                v = -min(sr[0], sr[1])
                thr = c["lock"]["thr"]
                if v > thr:
                    trig["lock"] = 0.5 + 0.5 * min(1.0, (v - thr) / self._ramp(c["lock"]))
            if t["gas"] > 0.2 and t["speed"] > 3:
                v = max(sr[2], sr[3])
                thr = c["slip"]["thr"]
                if v > thr:
                    trig["slip"] = 0.5 + 0.5 * min(1.0, (v - thr) / self._ramp(c["slip"]))

            rr = t.get("rpm_ratio", 0.0)
            if rr > c["rev"]["thr"] and t["gas"] > 0.5:
                trig["rev"] = 1.0
            g = t.get("gear", 0)
            if self.last_gear is not None and g != self.last_gear:
                trig["shift"] = 1.0
            self.last_gear = g
            self._brake_limiter(t, trig, now)
            self._gear_events(g, trig, now)
        else:
            self.last_gear = None
            self.blim_on = False
            for d in self.gear_det.values():
                d.update(stable=None, cand=None, fwd=None)

        test = self.test
        for k in EFFECTS:
            ck = c[k]
            en = ck["enabled"]
            if test and test[0] == k and now < test[1]:
                trig[k] = 1.0
                en = True
            if not en:
                # efekt kapali: durumu, bekleyen titresimi ve kilitleri sifirla (motor cikisi 0'a duser;
                # tekrar acilinca eski bir titresim kalintisi calmaz)
                self.state[k] = (0.0, 0.0)
                self.active[k] = False
                if k == "blim":
                    self.blim_on = False
                continue
            sev, until = self.state[k]
            if trig[k] > 0:
                sev, until = trig[k], now + max(ck["hold"], 10 if k in ("blim", "gup", "gdown") else 0) / 1000.0
            self.state[k] = (sev, until)
            self.active[k] = now < until

        out = [(0, 0, 50)] * MOTOR_COUNT
        for k in EFFECTS:
            if self.active[k]:
                targets = effect_motors(c[k], k)
                pct = self._effect_pct(c[k], self.state[k][0])
                for mm in targets:
                    pwm = self.motor_pwm(mm, pct)
                    if pwm > out[mm][0]:
                        out = list(out)
                        out[mm] = (pwm, int(round(c[k]["freq"] * 10)), int(c[k].get("duty", 50)))
        return list(out)

    @staticmethod
    def _gain(ck):
        """Hassasiyet (%50 = 1.0) -> kazanc 0.2..3.0."""
        try:
            return min(3.0, max(0.2, float(ck.get("sens", 50)) / 50.0))
        except (TypeError, ValueError):
            return 1.0

    def _ramp(self, ck):
        """Kilit/kayma efektinde esikten tam siddete cikis genisligi (eski sabit 0.5; hassasiyet %50 = ayni)."""
        return 0.5 / self._gain(ck)

    @staticmethod
    def _effect_pct(ck, sev):
        """Siddet(%) x efekt siddeti, efektin kendi min/max guc araligina yerlestirilir (0-100)."""
        pct = min(100.0, max(0.0, float(ck["intensity"]))) * sev
        if pct <= 0:
            return 0.0
        lo = min(100.0, max(0.0, float(ck.get("min_pct", 0))))
        hi = min(100.0, max(0.0, float(ck.get("max_pct", 100))))
        hi = max(hi, lo)
        return lo + (hi - lo) * pct / 100.0

    def _brake_limiter(self, t, trig, now):
        """Fren pedali esige ulasinca titresim. Histerezis: acilma thr'de, kapanma thr-hyst'in altinda;
        esik civarinda titresim surekli acilip kapanmaz. Siddet esikte %50'den baslar, full'de %100'e ulasir
        (hicbir zaman ayarli guc sinirini asmaz). ABS/kilit efektlerinden bagimsizdir."""
        b = self.cfg["blim"]
        try:
            thr = min(0.99, max(0.05, float(b["thr"]) / 100.0))
            hyst = min(thr, max(0.0, float(b.get("hyst", 5)) / 100.0))
            full = max(thr + 0.01, min(1.0, float(b.get("full", 100)) / 100.0))
        except (TypeError, ValueError):
            return
        br = t["brake"]
        if self.blim_on:
            if br < thr - hyst:
                self.blim_on = False
        elif br >= thr:
            self.blim_on = True
        if self.blim_on:
            frac = min(1.0, max(0.0, (br - thr) / (full - thr)))
            trig["blim"] = min(1.0, 0.5 + 0.5 * min(1.0, frac * self._gain(b)))

    def _gear_events(self, g, trig, now):
        """Vites yukseldi/dustu: HER vites degisimi tek olay. Vites, tepki hassasiyetine gore belirlenen sure
        kararli kalinca onaylanir (N'den gecis titremesi tekrar tetiklemez). Yalnizca ileri vitesler arasi
        degisim sayilir (R/N'ye gecis olay degildir)."""
        ng = norm_gear(self.src.NAME, g)
        if ng is None:
            return
        for key in ("gup", "gdown"):
            d = self.gear_det[key]
            if d["stable"] is None:
                d["stable"] = ng
                if ng >= 1:
                    d["fwd"] = ng
                continue
            if ng == d["stable"]:
                d["cand"] = None
                continue
            if d["cand"] is None or d["cand"][0] != ng:
                d["cand"] = (ng, now)
            delay = (100.0 - min(100.0, max(0.0, float(self.cfg[key].get("sens", 80))))) / 100.0 * GEAR_CONFIRM_MAX_S
            if now - d["cand"][1] < delay:
                continue
            d["stable"], d["cand"] = ng, None
            if ng >= 1:
                old = d["fwd"]
                d["fwd"] = ng
                if old is not None and ((key == "gup" and ng > old) or (key == "gdown" and ng < old)):
                    trig[key] = 1.0
            elif ng < 0:
                d["fwd"] = None

    def motor_pwm(self, m, pct):
        """Yuzde siddeti, motorun min/max guc ayarina gore 0-255 PWM'e cevirir."""
        if pct <= 0:
            return 0
        mc = self.mcfg
        top = 255.0 * min(100.0, max(1.0, mc.get("max%d" % (m + 1), 100))) / 100.0
        lo = min(float(mc.get("min%d" % (m + 1), 0)), top)
        return max(1, int(round(lo + (top - lo) * min(100.0, pct) / 100.0)))

    def run(self):
        loops, t0 = 0, time.perf_counter()
        while self.running:
            now = time.perf_counter()
            if self.pending_source:
                self.src.close()
                self.src = SOURCES[self.pending_source]()
                self.pending_source = None
                self.last_pid = None
                self.last_change = now
            t = self.src.read()
            if self.auto and now - self.last_probe > 1.0 and not (t and now - self.last_change < 0.5):
                self.last_probe = now
                found = probe_games()
                if found and found != self.src.NAME:
                    self.pending_source = found
            live = False
            if t:
                if t["packetId"] != self.last_pid:
                    self.last_pid = t["packetId"]
                    self.last_change = now
                age = now - self.last_change
                live = age < 0.5 and t["valid"]
                if age > 2.0:
                    self.src.close()
                    self.last_change = now
            if not live:
                for k in EFFECTS:
                    self.state[k] = (0.0, 0.0)
            out = self.compute(t if live else None, now)
            self.snap = {"t": t, "live": live, "out": out, "active": dict(self.active),
                         "valid": (t["valid"] if t else True)}
            self.send(out, now)
            loops += 1
            if now - t0 >= 1.0:
                self.hz = loops / (now - t0)
                loops, t0 = 0, now
            time.sleep(0.002)
        self.disconnect()
