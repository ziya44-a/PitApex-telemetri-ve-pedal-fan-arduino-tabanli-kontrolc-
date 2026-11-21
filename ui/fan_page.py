"""02 - Fan sayfasi: araç hızına bağlı fan kontrolü (pedal sisteminden bağımsız çalışır).

İKİ FAN YUVASI: her fan kendi motor çıkışını (M1-M4), açık/kapalı ayarını ve hız eğrisini taşır. Üstte yuvalar
tek tabloda özetlenir (Açık / Çıkış / Durum); altta her fan için ayrı sekme vardır."""
import json
import time
import tkinter as tk
from tkinter import ttk

from core.outputs import conflicts, out_name
from hardware.fan import DEFAULT_OUTPUTS, FAN_COUNT, curve_pct, default_fans, normalize_fans, normalized

NO_DATA_CHOICES = ["Fan dursun", "Rölantide kalsın"]
OUTPUT_CHOICES = ["Seçilmedi", "M1", "M2", "M3", "M4"]          # indeks = çıkış numarası (0 = seçilmedi)

HARDWARE_NOTE = (
    "Donanım notları\n"
    "• Her fan motor shield'in bir çıkışına (M1-M4) bağlanır; çıkışı yukarıdan seçersin. Bir çıkışa yalnızca tek cihaz "
    "(fan ya da pedal motoru) bağlanmalıdır; aynı çıkış iki işte seçilirse uyarı çıkar.\n"
    "• İki fan ve M3/M4 titreşim motoru için Arduino kodu v4 gerekir (firmware/PedalHaptic.ino). Kod v3 ise tek fan "
    "çalışır ve çıkışı kodda sabittir (LEGACY_FAN_MOTOR).\n"
    "• L293D kanal başına yaklaşık 0,6 A sürekli (1,2 A tepe) verebilir. Fan etiketindeki akım bunun altında, "
    "tercihen 0,4 A altında olmalı. 12 V, 0,1-0,3 A'lik 2 veya 3 telli fanlar uygundur. Büyük kasa fanları ve "
    "4 telli PWM fanlar bu çıkışa doğrudan bağlanmamalı; onlar için harici MOSFET sürücü gerekir.\n"
    "• Fan PWM frekansı sabit yaklaşık 1 kHz'dir (değiştirilemez). Bazı fanlar düşük hızda hafif ses çıkarabilir.\n"
    "• Fanlar ve titreşim motorları aynı motor beslemesini paylaşır; besleme zayıfsa iki fan birlikte çalışırken pedal "
    "titreşimi zayıflayabilir.\n"
    "• Min PWM: fanın kendiliğinden dönmeye başladığı en düşük değerdir. Fan düşük hızda duruyorsa yükselt."
)
LEVEL_STYLE = {"ok": "Ok.TLabel", "warn": "Warn.TLabel", "bad": "Bad.TLabel"}


class FanPanel:
    """Tek fan yuvasının arayüzü ve ayarı (sekme içeriği + yuva satırı değişkenleri)."""

    CURVE = (("idle_pct", "Rölanti gücü % (0 km/h)", 0, 100, "%.0f", 1),
             ("mid_speed", "Orta nokta hızı (km/h)", 10, 500, "%.0f", 5),
             ("mid_pct", "Orta nokta gücü %", 0, 100, "%.0f", 1),
             ("max_speed", "Maksimum hız (km/h)", 50, 600, "%.0f", 5),
             ("max_pct", "Güç sınırı % (en yüksek)", 10, 100, "%.0f", 1))
    FINE = (("min_pwm", "Min PWM (0-255)", 0, 200, "%.0f", 1),
            ("kick_ms", "Kalkış darbesi ms (0=kapalı)", 0, 2000, "%.0f", 50),
            ("ramp_up", "Artış hızı %/sn", 5, 500, "%.0f", 5),
            ("ramp_down", "Azalış hızı %/sn", 5, 500, "%.0f", 5))

    def __init__(self, page, index, saved):
        self.page, self.index = page, index
        c = normalized(saved, DEFAULT_OUTPUTS[index])
        self.vars = {
            "enabled": tk.BooleanVar(value=c["enabled"]),
            "output": tk.StringVar(value=OUTPUT_CHOICES[c["output"]]),
            "no_data": tk.StringVar(value=NO_DATA_CHOICES[1 if c["no_data"] == "idle" else 0]),
        }
        for k in ("idle_pct", "mid_speed", "mid_pct", "max_speed", "max_pct", "min_pwm", "kick_ms", "ramp_up", "ramp_down"):
            self.vars[k] = tk.DoubleVar(value=c[k])
        self.test_var = tk.DoubleVar(value=50)
        self.cfg = c
        self.canvas = None
        self.detail_lbl = None

    # ---------- arayüz ----------
    def build_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        ctl = ttk.Frame(parent)
        ctl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ttk.Label(ctl, text="Telemetri yokken:").grid(row=0, column=0, padx=(0, 4))
        ttk.Combobox(ctl, textvariable=self.vars["no_data"], values=NO_DATA_CHOICES, state="readonly",
                     width=18).grid(row=0, column=1, padx=4)
        self.detail_lbl = ttk.Label(ctl, text="", style="Muted.TLabel")
        self.detail_lbl.grid(row=0, column=2, padx=16, sticky="w")

        mid = ttk.Frame(parent)
        mid.grid(row=1, column=0, sticky="ew")
        mid.columnconfigure(0, weight=1)
        cf = ttk.LabelFrame(mid, text="Hız → fan gücü eğrisi")
        cf.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        for r, spec in enumerate(self.CURVE):
            self.slider(cf, r, *spec)
        self.canvas = tk.Canvas(mid, width=340, height=190, highlightthickness=0, bg=self.page.app.theme.c["panel"])
        self.canvas.grid(row=0, column=1, padx=6, pady=4, sticky="n")

        ad = ttk.LabelFrame(parent, text="İnce ayar")
        ad.grid(row=2, column=0, sticky="ew", padx=6, pady=4)
        for r, spec in enumerate(self.FINE):
            self.slider(ad, r, *spec)

        tf = ttk.LabelFrame(parent, text="Fan testi (oyun gerekmez)")
        tf.grid(row=3, column=0, sticky="ew", padx=6, pady=4)
        ttk.Label(tf, text="Güç %").grid(row=0, column=0, padx=6)
        ttk.Scale(tf, from_=0, to=100, variable=self.test_var, length=220).grid(row=0, column=1, padx=4, pady=6)
        ttk.Button(tf, text="Test (5 sn)", command=self.start_test).grid(row=0, column=2, padx=4)
        ttk.Button(tf, text="Durdur", command=lambda: self.page.app.fan.stop_test(self.index)).grid(row=0, column=3, padx=4)

    def slider(self, parent, row, key, text, lo, hi, fmt, step):
        var = self.vars[key]
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=6)

        def snap(v):
            var.set(round(round(float(v) / step) * step, 3))
        ttk.Scale(parent, from_=lo, to=hi, variable=var, length=190, command=snap).grid(row=row, column=1, padx=4)
        ttk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=var, width=7, format=fmt).grid(
            row=row, column=2, padx=4, pady=2)

    def start_test(self):
        try:
            self.page.app.fan.start_test(float(self.test_var.get()), 5.0, self.index)
        except Exception:
            pass

    # ---------- ayar ----------
    def sync(self):
        raw = {}
        for k, var in self.vars.items():
            try:
                raw[k] = var.get()
            except Exception:
                raw[k] = self.cfg.get(k)          # kutu geçici boşsa eskisini koru
        raw["no_data"] = "idle" if raw.get("no_data") == NO_DATA_CHOICES[1] else "stop"
        out = raw.get("output")
        raw["output"] = OUTPUT_CHOICES.index(out) if out in OUTPUT_CHOICES else self.cfg.get("output", 0)
        self.cfg = normalized(raw, DEFAULT_OUTPUTS[self.index])

    def apply(self, cfg):
        c = normalized(cfg, DEFAULT_OUTPUTS[self.index])
        for k, v in c.items():
            if k == "no_data":
                self.vars[k].set(NO_DATA_CHOICES[1 if v == "idle" else 0])
            elif k == "output":
                self.vars[k].set(OUTPUT_CHOICES[v])
            elif k in self.vars:
                self.vars[k].set(v)
        self.cfg = c

    def draw_curve(self, speed):
        cv, c = self.canvas, self.page.app.theme.c
        cv.configure(bg=c["panel"])
        cv.delete("all")
        w, h, l, b, t, r = 340, 190, 36, 26, 10, 10
        cv.create_line(l, h - b, w - r, h - b, fill=c["muted"])
        cv.create_line(l, t, l, h - b, fill=c["muted"])
        mx = max(self.cfg["max_speed"], 50.0)
        sx = lambda v: l + (w - l - r) * min(v, mx) / mx
        sy = lambda p: (h - b) - (h - b - t) * p / 100.0
        for p in (0, 50, 100):
            cv.create_text(l - 4, sy(p), text="%d" % p, anchor="e", fill=c["muted"], font=("Segoe UI", 8))
            cv.create_line(l, sy(p), w - r, sy(p), fill=c["border"], dash=(2, 4))
        cv.create_text(w - r, h - 10, text="km/h", anchor="e", fill=c["muted"], font=("Segoe UI", 8))
        cv.create_text(l, h - 10, text="0", anchor="w", fill=c["muted"], font=("Segoe UI", 8))
        cv.create_text(w - r - 30, h - 10, text="%d" % mx, anchor="e", fill=c["muted"], font=("Segoe UI", 8))
        pts = []
        for i in range(0, 61):
            v = mx * i / 60.0
            pts += [sx(v), sy(curve_pct(v, self.cfg))]
        cv.create_line(*pts, fill=c["accent"], width=2)
        if speed is not None:
            x, y = sx(speed), sy(curve_pct(speed, self.cfg))
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, fill=c["live"], outline="")


class FanPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        saved = normalize_fans(app.prefs.get("fan", {}) or {})
        self.panels = [FanPanel(self, i, saved[i]) for i in range(FAN_COUNT)]
        self.status_lbls = []
        self.out_boxes = []
        self._last_saved = json.dumps(self.get_cfg(), sort_keys=True)
        self._last_save_t = time.time()
        self.build()

    # ---------------- arayüz ----------------
    def build(self):
        self.columnconfigure(0, weight=1)
        sl = ttk.LabelFrame(self, text="Fan yuvaları ve çıkışlar")
        sl.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        sl.columnconfigure(3, weight=1)
        for col, text in enumerate(("Yuva", "Açık", "Çıkış (motor shield)", "Durum")):
            ttk.Label(sl, text=text, style="Muted.TLabel").grid(row=0, column=col, sticky="w", padx=8, pady=(4, 0))
        for i, p in enumerate(self.panels):
            r = 1 + i
            ttk.Label(sl, text="Fan %d" % (i + 1), style="Big.TLabel").grid(row=r, column=0, sticky="w", padx=8, pady=4)
            ttk.Checkbutton(sl, variable=p.vars["enabled"], text="").grid(row=r, column=1, sticky="w", padx=8)
            box = ttk.Combobox(sl, textvariable=p.vars["output"], values=OUTPUT_CHOICES, state="readonly", width=12)
            box.grid(row=r, column=2, sticky="w", padx=8)
            self.out_boxes.append(box)
            lb = ttk.Label(sl, text="", style="Muted.TLabel")
            lb.grid(row=r, column=3, sticky="w", padx=8)
            self.status_lbls.append(lb)
        self.warn_lbl = ttk.Label(sl, text="", style="Bad.TLabel", wraplength=860, justify="left")
        self.warn_lbl.grid(row=3, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 4))
        ttk.Label(sl, text="Hız bilgisi, pedal sayfasında seçili/algılanan oyundan gelir; pedal efektleri kapalı olsa da "
                           "fanlar çalışır. Aynı çıkışı bir fan ve bir pedal efekti birlikte kullanamaz.",
                  style="Muted.TLabel", wraplength=860, justify="left").grid(
            row=4, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 6))

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=1, column=0, sticky="ew", padx=6, pady=4)
        for i, p in enumerate(self.panels):
            tab = ttk.Frame(self.nb)
            self.nb.add(tab, text=self.tab_title(i))
            p.build_tab(tab)

        ttk.Label(self, text=HARDWARE_NOTE, style="Muted.TLabel", justify="left", wraplength=900).grid(
            row=2, column=0, sticky="w", padx=10, pady=(6, 8))

    def tab_title(self, i):
        return "Fan %d (%s)" % (i + 1, out_name(self.panels[i].cfg["output"]))

    # ---------------- ayar eşitleme ----------------
    def sync(self):
        for p in self.panels:
            p.sync()

    def get_cfg(self):
        """Kaydedilen ve fan ipliğinin okuduğu ayar: {"fans": [fan1, fan2]} (Tk değişkenleri değil, sözlük)."""
        return {"fans": [p.cfg for p in self.panels]}

    def autosave(self):
        if time.time() - self._last_save_t < 3:
            return
        self._last_save_t = time.time()
        snap = json.dumps(self.get_cfg(), sort_keys=True)
        if snap != self._last_saved:
            self.app.prefs.set("fan", self.get_cfg())
            self._last_saved = snap

    def load_prefs(self, raw):
        """Kayıtlı (eski tek fan ya da yeni iki fan) ayarı arayüze yükler. İçe aktarmada da kullanılır."""
        fans = normalize_fans(raw or {})
        for p, c in zip(self.panels, fans):
            p.apply(c)
        self.mark_saved()

    def mark_saved(self):
        self._last_saved = json.dumps(self.get_cfg(), sort_keys=True)

    def reset_after_wipe(self):
        for p, c in zip(self.panels, default_fans()):
            p.apply(c)
        self.mark_saved()                         # temizlenen veri kendiliğinden geri yazılmasın

    # ---------------- görsel güncelleme ----------------
    def warnings(self):
        link = self.app.link
        fans = [p.cfg for p in self.panels]
        msgs = ["⚠ " + t + ": farklı bir çıkış seç" for _n, _k, t in conflicts(self.app.cfg, fans)]
        v = link.fw_version
        if link.connected and v is not None and not link.multi_output:
            if fans[1]["enabled"]:
                msgs.append("⚠ Arduino kodu v%s: ikinci fan ve çıkış seçimi için firmware v4 yükle" % v)
        return "\n".join(msgs)

    def tick(self, visible):
        self.sync()
        self.autosave()
        if not visible:
            return
        stats = self.app.fan.statuses
        for i, p in enumerate(self.panels):
            s = stats[i]
            self.status_lbls[i].config(text=s["text"], style=LEVEL_STYLE.get(s["level"], "Muted.TLabel"))
            sp = "%.0f km/h" % s["speed"] if s["speed"] is not None else "—"
            p.detail_lbl.config(text="Araç hızı: %s   |   Fan gücü: %%%.0f   |   PWM: %d/255" % (sp, s["pct"], s["pwm"]))
            p.draw_curve(s["speed"])
            try:
                self.nb.tab(i, text=self.tab_title(i))
            except Exception:
                pass
        self.warn_lbl.config(text=self.warnings())
