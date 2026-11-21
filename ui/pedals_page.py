from ui.i18n import translate
"""01 - Pedallar sayfasi. Eski PedalHaptic arayuzunun (efektler, motor ince ayari, profiller, canli telemetri)
ayni widget ve ayni ayar mantigiyla tasinmis halidir."""
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox

from core.engine import (DEFAULT_MOTORS, DEFAULTS, EFFECTS, M3M4_FW_MIN, MOTOR_COUNT, MOTOR_NAMES, PWM_CHOICES,
                         effect_motors)
from core.outputs import conflicts
from telemetry.legacy_sources import HINTS, SOURCES

# Efekt detay ayarlari (acilinca gorunur): (alan, etiket, min, maks, bicim, adim)
_POWER = [("intensity", "Motor gücü / şiddet %", 0, 100, "%.0f", 1),
          ("min_pct", "Minimum güç %", 0, 100, "%.0f", 1),
          ("max_pct", "Maksimum güç %", 0, 100, "%.0f", 1)]
_WAVE = [("freq", "Frekans Hz (0=sürekli)", 0, 80, "%.1f", 0.5),
         ("duty", "Darbe oranı %", 5, 95, "%.0f", 1)]
_THR = ("thr", "Aktivasyon eşiği", 0.0, 1.0, "%.2f", 0.01)
_HOLD = ("hold", "Tutma süresi ms", 0, 300, "%.0f", 5)
_SENS_RAMP = ("sens", "Hassasiyet % (50=varsayılan)", 10, 100, "%.0f", 5)
FIELDS = {
    "abs":   _POWER + _WAVE + [_THR, _HOLD],
    "lock":  _POWER + _WAVE + [_THR, _SENS_RAMP, _HOLD],
    "tc":    _POWER + _WAVE + [_THR, _HOLD],
    "slip":  _POWER + _WAVE + [_THR, _SENS_RAMP, _HOLD],
    "rev":   _POWER + _WAVE + [("thr", "Devir eşiği (0-1)", 0.0, 1.0, "%.2f", 0.01), _HOLD],
    "shift": _POWER + _WAVE + [("hold", "Titreşim süresi ms", 0, 300, "%.0f", 5)],
    "blim":  _POWER + _WAVE + [("thr", "Aktivasyon fren %", 10, 99, "%.0f", 1),
                               ("full", "Tam güç fren %", 20, 100, "%.0f", 1),
                               ("hyst", "Histerezis % (kapanma payı)", 0, 30, "%.0f", 1),
                               ("sens", "Hassasiyet % (50=varsayılan)", 10, 100, "%.0f", 5),
                               ("hold", "Tutma süresi ms", 0, 300, "%.0f", 5)],
    "gup":   _POWER + _WAVE + [("hold", "Titreşim süresi ms", 10, 500, "%.0f", 5),
                               ("sens", "Tepki hassasiyeti % (100=anında)", 0, 100, "%.0f", 5)],
    "gdown": _POWER + _WAVE + [("hold", "Titreşim süresi ms", 10, 500, "%.0f", 5),
                               ("sens", "Tepki hassasiyeti % (100=anında)", 0, 100, "%.0f", 5)],
}
HELP = {
    "lock": "Hassasiyet: kayma eşiği aşıldığında şiddetin ne kadar hızlı tam güce çıktığı.",
    "slip": "Hassasiyet: kayma eşiği aşıldığında şiddetin ne kadar hızlı tam güce çıktığı.",
    "blim": "Fren, aktivasyon %'sine ulaşınca başlar; tam güç %'sinde ayarlı gücün üstüne çıkmaz. Titreşim, "
            "aktivasyondan histerezis payı kadar aşağı inene dek sürer (eşikte titrek açılıp kapanmaz).",
    "gup":   "Vites yükselince tek bir titreşim. Düşük hassasiyet, vitesin kararlı kalmasını bekler (N geçişini eler).",
    "gdown": "Vites düşünce tek bir titreşim. Düşük hassasiyet, vitesin kararlı kalmasını bekler (N geçişini eler).",
}
COLUMNS = (("abs", "lock", "blim", "tc"), ("slip", "rev", "shift", "gup", "gdown"))


class PedalsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.cfg = app.cfg
        self.engine = app.engine
        self.vars = {}
        self.details = {}
        self.motors = {}          # efekt -> atanan motor listesi (0 tabanli: 0=M1 ... 3=M4)
        self.slot_ui = {}         # efekt -> {"frame": çerçeve, "warn": uyarı etiketi}
        self._last_saved = None
        self._last_autosave = time.time()
        self.build_ui()
        self.load_settings()
        self._last_saved = self._snapshot()

    def _queue_scrollregion_update(self, event=None):
        """Coalesce Tk geometry updates during interactive window resizing."""
        if self._scrollregion_job is not None:
            try:
                self.after_cancel(self._scrollregion_job)
            except tk.TclError:
                pass
        self._scrollregion_job = self.after(75, self._refresh_scrollregion)

    def _refresh_scrollregion(self):
        self._scrollregion_job = None
        if self.canvas.winfo_exists():
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_resized(self, event):
        if event.width != self._last_canvas_width:
            self._last_canvas_width = event.width
            self.canvas.itemconfigure(self._win, width=event.width)
            self._queue_scrollregion_update()

    # ---------------- arayuz ----------------
    def build_ui(self):
        # sayfa uzun olabilir (acik efektler): kaydirilabilir govde
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.app.theme.c["bg"])
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.body = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=1)
        self._scrollregion_job = None
        self._last_canvas_width = None
        self.body.bind("<Configure>", self._queue_scrollregion_update)
        self.canvas.bind("<Configure>", self._canvas_resized)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        r = self.body
        gf = ttk.LabelFrame(r, text="Oyun (pedal titreşimi için telemetri kaynağı)")
        gf.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        self.src_var = tk.StringVar(value="ACC")
        self.auto_var = tk.BooleanVar(value=True)
        btns = ttk.Frame(gf)
        btns.pack(side="left", padx=2, pady=2)
        for i, name in enumerate(("ACC", "AC", "LMU", "iRacing", "BeamNG", "ETS2")):
            ttk.Radiobutton(btns, text=name, value=name, variable=self.src_var, style="Toolbutton",
                            width=8, command=self.change_source).grid(row=0, column=i, padx=3, pady=2)
        ttk.Checkbutton(gf, text="Otomatik algıla", variable=self.auto_var).pack(side="left", padx=12)

        tel = ttk.LabelFrame(r, text="Canlı telemetri")
        tel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        self.game_lbl = ttk.Label(tel, text="Bekleniyor...")
        self.game_lbl.grid(row=0, column=0, columnspan=4, sticky="w", padx=4)
        self.bars = {}
        for i, (key, text) in enumerate([("gas", "Gaz"), ("brake", "Fren"), ("abs", "ABS"), ("tc", "TC")]):
            ttk.Label(tel, text=text, width=6).grid(row=1 + i, column=0, sticky="w", padx=4)
            pb = ttk.Progressbar(tel, maximum=100, length=220)
            pb.grid(row=1 + i, column=1, padx=4, pady=1)
            self.bars[key] = pb
        self.val_lbl = ttk.Label(tel, text="", justify="left")
        self.val_lbl.grid(row=1, column=2, rowspan=4, padx=14, sticky="w")
        self.ind = {}
        indf = ttk.Frame(tel)
        indf.grid(row=1, column=3, rowspan=4, padx=8)
        c = self.app.theme.c
        for i, (k, info) in enumerate(EFFECTS.items()):
            lb = tk.Label(indf, text=info["name"], width=26, bg=c["ind_off"], fg=c["muted"], anchor="w")
            lb.grid(row=i % 5, column=i // 5, padx=2, pady=1)
            self.ind[k] = lb

        ef = ttk.LabelFrame(r, text="Efektler (kutucukla aç; detaylar açılınca görünür)")
        ef.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        ef.columnconfigure(0, weight=1, uniform="eff")
        ef.columnconfigure(1, weight=1, uniform="eff")
        for col, keys in enumerate(COLUMNS):
            stack = ttk.Frame(ef)
            stack.grid(row=0, column=col, sticky="new", padx=4, pady=2)
            for k in keys:
                self.build_effect(stack, k, EFFECTS[k])

        mf = ttk.LabelFrame(r, text="Motor ince ayarı")
        mf.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        self.mvars = {"pwm": tk.StringVar(value=PWM_CHOICES[DEFAULT_MOTORS["pwm"]])}
        ttk.Label(mf, text="Motor PWM frekansı (yalnız M1+M2 ortak; M3/M4 sabit 1 kHz)").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Combobox(mf, textvariable=self.mvars["pwm"], values=PWM_CHOICES, state="readonly",
                     width=22).grid(row=0, column=1, columnspan=2, sticky="w", pady=2)
        for i, m in enumerate(("1", "2", "3", "4")):
            fr = ttk.LabelFrame(mf, text="Motor %s (M%s)" % (m, m))
            fr.grid(row=1 + i // 2, column=(i % 2) * 3, columnspan=3, sticky="ew", padx=4, pady=2)
            self.mvars["min" + m] = tk.DoubleVar(value=DEFAULT_MOTORS["min" + m])
            self.mvars["max" + m] = tk.DoubleVar(value=DEFAULT_MOTORS["max" + m])
            self.slider(fr, 0, "Min güç (0-255)", self.mvars["min" + m], 0, 200, "%.0f", 1)
            self.slider(fr, 1, "Max güç %", self.mvars["max" + m], 20, 100, "%.0f", 1)
        ttk.Label(mf, text="Min güç: motorun dönmeye başladığı en düşük değer. %1 şiddette bile "
                           "dönsün istiyorsan yükselt. M3/M4 için Arduino kodu v4 gerekir.", style="Muted.TLabel").grid(
            row=3, column=0, columnspan=6, sticky="w", padx=4)

        pf = ttk.LabelFrame(r, text="Profiller")
        pf.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        self.prof_var = tk.StringVar()
        self.prof_box = ttk.Combobox(pf, textvariable=self.prof_var, width=24)
        self.prof_box.grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(pf, text="Kaydet", command=self.save_profile).grid(row=0, column=1, padx=2)
        ttk.Button(pf, text="Yükle", command=self.load_profile).grid(row=0, column=2, padx=2)
        ttk.Button(pf, text="Varsayılana dön", command=self.reset_defaults).grid(row=0, column=3, padx=2)
        self.refresh_profiles()

    def build_effect(self, parent, key, info):
        """Bağımsız kart: kapalıyken yalnız kutucuk + ad; açılınca detaylar aşağı genişler."""
        card = ttk.Frame(parent, relief="solid", borderwidth=1)
        card.pack(fill="x", pady=3)
        card.columnconfigure(0, weight=1)
        v = {}
        for f, dv in DEFAULTS[key].items():
            if f == "enabled":
                v[f] = tk.BooleanVar(value=dv)
            elif f == "motors":
                self.motors[key] = list(dv)
            else:
                v[f] = tk.DoubleVar(value=dv)
        self.vars[key] = v
        ttk.Checkbutton(card, text=info["name"], variable=v["enabled"],
                        command=lambda k=key: self.toggle_effect(k)).grid(row=0, column=0, sticky="w", padx=6, pady=3)
        d = ttk.Frame(card)
        d.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        self.details[key] = d
        ttk.Label(d, text="Motor(lar)").grid(row=0, column=0, sticky="nw", padx=4, pady=4)
        slots = ttk.Frame(d)
        slots.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        self.slot_ui[key] = {"frame": slots, "warn": None, "boxes": []}
        ttk.Button(d, text="Test (1 sn)", command=lambda k=key: self.test_effect(k)).grid(row=0, column=2, sticky="n")
        self.render_slots(key)
        for i, (f, label, lo, hi, fmt, step) in enumerate(FIELDS[key]):
            self.slider(d, 1 + i, label, v[f], lo, hi, fmt, step)
        if key in HELP:
            ttk.Label(d, text=HELP[key], style="Muted.TLabel", wraplength=340, justify="left").grid(
                row=1 + len(FIELDS[key]), column=0, columnspan=3, sticky="w", padx=4, pady=(2, 0))
        self.update_expand(key)

    # ---------------- motor yuvalari (M1-M4, efekt başına bir veya birden çok motor) ----------------
    def render_slots(self, key):
        """Efektin motor seçim satırlarını yeniden çizer: her satır bir motor; son satırın altında '+ Motor ekle'."""
        ui = self.slot_ui[key]
        fr = ui["frame"]
        for w in list(fr.winfo_children()):
            w.destroy()
        ui["boxes"] = []
        chosen = self.motors[key]
        for idx, m in enumerate(chosen):
            row = ttk.Frame(fr)
            row.grid(row=idx, column=0, sticky="w", pady=1)
            others = {x for j, x in enumerate(chosen) if j != idx}
            box = ttk.Combobox(row, values=[n for i, n in enumerate(MOTOR_NAMES) if i not in others], state="readonly", width=8)
            box.set(MOTOR_NAMES[m])
            box.grid(row=0, column=0, padx=(0, 4))
            box.bind("<<ComboboxSelected>>", lambda e, k=key, i=idx, b=box: self.pick_motor(k, i, b.get()))
            ui["boxes"].append(box)
            if idx > 0:
                ttk.Button(row, text="✕", width=3, command=lambda k=key, i=idx: self.remove_motor(k, i)).grid(row=0, column=1)
        if len(chosen) < MOTOR_COUNT:
            ttk.Button(fr, text="＋ Motor ekle", command=lambda k=key: self.add_motor(k)).grid(
                row=len(chosen), column=0, sticky="w", pady=(3, 0))
        ui["warn"] = ttk.Label(fr, text="", style="Warn.TLabel", wraplength=300, justify="left")
        ui["warn"].grid(row=len(chosen) + 1, column=0, sticky="w")

    def pick_motor(self, key, idx, name):
        if name in MOTOR_NAMES:
            m = MOTOR_NAMES.index(name)
            if m not in [x for j, x in enumerate(self.motors[key]) if j != idx]:
                self.motors[key][idx] = m
        self.render_slots(key)
        self.sync_cfg()

    def add_motor(self, key):
        """İlk boş motoru ekler (örn. ABS için M1 seçiliyken M2 eklenir). Kullanıcı sonra başka motora çevirebilir."""
        free = [i for i in range(MOTOR_COUNT) if i not in self.motors[key]]
        if free:
            self.motors[key].append(free[0])
            self.render_slots(key)
            self.sync_cfg()

    def remove_motor(self, key, idx):
        if len(self.motors[key]) > 1 and 0 < idx < len(self.motors[key]):
            del self.motors[key][idx]
            self.render_slots(key)
            self.sync_cfg()

    def slot_warnings(self):
        """Efekt başına uyarılar: aynı çıkış fanda da seçili / M3-M4 için Arduino kodu eski."""
        out = {k: [] for k in self.motors}
        try:
            fans = self.app.fan_page.get_cfg()["fans"]
            link = self.app.link
        except Exception:
            return out
        for n, kind, _t in conflicts(self.cfg, fans):
            if kind != "pedal+fan":
                continue
            f = [i + 1 for i, x in enumerate(fans) if x["enabled"] and x["output"] == n]
            for k in self.motors:
                if self.cfg.get(k, {}).get("enabled") and (n - 1) in self.motors[k]:
                    out[k].append("⚠ M%d aynı anda Fan %s'de de seçili" % (n, "/".join(map(str, f))))
        v = link.fw_version
        if link.connected and v is not None and v < M3M4_FW_MIN:
            for k, lst in self.motors.items():
                if any(m >= 2 for m in lst):
                    out[k].append("⚠ M3/M4 için Arduino kodu v4 gerekli (şu an v%s)" % v)
        return out

    def update_expand(self, key=None):
        """Açık efektin detayları görünür, kapalı efekt yalnızca kutucuk + ad olarak kalır."""
        for k in ([key] if key else list(self.details)):
            if self.vars[k]["enabled"].get():
                self.details[k].grid()
            else:
                self.details[k].grid_remove()

    def toggle_effect(self, key):
        """Kutucuk değişti: ayarı hemen motora ilet (kapanan efektin çıkışı bir sonraki turda sıfırlanır)."""
        self.sync_cfg()
        self.update_expand(key)

    def slider(self, parent, row, text, var, lo, hi, fmt, step=1):
        """Kaydırıcı + yanında elle yazılabilen / oklarla ince ayarlanan sayı kutusu."""
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=4)

        def snap(v):
            var.set(round(round(float(v) / step) * step, 3))
        ttk.Scale(parent, from_=lo, to=hi, variable=var, length=150, command=snap).grid(row=row, column=1, padx=2)
        ttk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=var, width=6,
                    format=fmt).grid(row=row, column=2, padx=2, pady=1)

    def _wheel(self, e):
        try:
            self.canvas.yview_scroll(int(-e.delta / 120), "units")
        except Exception:
            pass

    # ---------------- kontrol ----------------
    def change_source(self):
        self.auto_var.set(False)  # elle seçince otomatik algılama kapanır
        self.engine.auto = False
        self.engine.pending_source = self.src_var.get()

    def test_effect(self, key):
        self.engine.test = (key, time.perf_counter() + 1.0)

    # ---------------- ayarlar ----------------
    def sync_cfg(self):
        for k, v in self.vars.items():
            for f, var in v.items():
                try:  # kutuya yazarken geçici boş/geçersiz değer olabilir: eskisini koru
                    self.cfg[k][f] = var.get()
                except Exception:
                    pass
            self.cfg[k]["motors"] = list(self.motors.get(k, DEFAULTS[k]["motors"]))
            self.cfg[k].pop("motor", None)             # eski tek-motor anahtarı: yeni liste onun yerine geçer
        mc = self.cfg["_motors"]
        for f, var in self.mvars.items():
            try:
                if f == "pwm":
                    val = var.get()
                    mc[f] = PWM_CHOICES.index(val) if val in PWM_CHOICES else 0
                else:
                    mc[f] = var.get()
            except Exception:
                pass

    def apply_cfg(self, data):
        self._apply_cfg(data)
        self.update_expand()

    def _apply_cfg(self, data):
        md = data.get("_motors", {}) if isinstance(data, dict) else {}
        for f, var in self.mvars.items():
            try:
                var.set(PWM_CHOICES[int(md[f])] if f == "pwm" else md[f])
            except Exception:
                pass
        for k in EFFECTS:
            ck = data.get(k) if isinstance(data, dict) else None
            if isinstance(ck, dict):
                # yeni 'motors' listesi ya da eski 'motor' (0=M1, 1=M2, 2=ikisi) -> liste
                self.motors[k] = effect_motors(ck, k)
            else:
                self.motors[k] = list(DEFAULTS[k]["motors"])
            self.render_slots(k)
            for f in DEFAULTS[k]:
                if f == "motors":
                    continue
                try:
                    self.vars[k][f].set(data[k][f])
                except Exception:
                    pass

    def _snapshot(self):
        self.sync_cfg()
        data = json.loads(json.dumps(self.cfg))
        data["_source"] = self.src_var.get()
        data["_auto"] = bool(self.auto_var.get())
        return json.dumps(data, sort_keys=True)

    def load_settings(self):
        data = self.app.pedal_store.load()
        if not data:
            return
        try:
            self.apply_cfg(data)
            if data.get("_source") in SOURCES:
                self.src_var.set(data["_source"])
                self.engine.pending_source = data["_source"]
            if "_auto" in data:
                self.auto_var.set(bool(data["_auto"]))
        except Exception:
            pass

    def save_settings(self, force=False):
        snap = self._snapshot()
        if not force and snap == self._last_saved:
            return
        if self.app.pedal_store.save(json.loads(snap)):
            self._last_saved = snap

    def autosave(self):
        """Elektrik kesintisi/çökme olursa ayar kaybolmasın: değişiklik varsa 10 snde bir yazar."""
        if time.time() - self._last_autosave > 10:
            self._last_autosave = time.time()
            self.save_settings()

    def reset_after_wipe(self):
        self.apply_cfg(DEFAULTS)
        self.prof_var.set("")
        self.refresh_profiles()
        self._last_saved = self._snapshot()      # temizlenen veri kendiliğinden geri yazılmasın

    # ---------------- profiller ----------------
    def refresh_profiles(self):
        self.prof_box["values"] = self.app.profiles.names()

    def save_profile(self):
        name = self.prof_var.get().strip()
        if not name:
            messagebox.showinfo("PitApex", "Profil adı yaz.")
            return
        self.sync_cfg()
        try:
            self.prof_var.set(self.app.profiles.save(name, self.cfg))
        except (ValueError, OSError) as e:
            messagebox.showerror("PitApex", "Profil kaydedilemedi:\n%s" % e)
            return
        self.refresh_profiles()

    def load_profile(self):
        data = self.app.profiles.load(self.prof_var.get().strip())
        if data is None:
            messagebox.showinfo("PitApex", "Profil bulunamadı.")
            return
        self.apply_cfg(data)

    def reset_defaults(self):
        self.apply_cfg(DEFAULTS)

    # ---------------- canlı güncelleme ----------------
    def tick(self, visible):
        """Her turda ayarları motora eşitler; görsel güncelleme sadece sayfa görünürken yapılır."""
        self.sync_cfg()
        e = self.engine
        e.auto = bool(self.auto_var.get())
        if e.auto and e.src.NAME != self.src_var.get() and not e.pending_source:
            self.src_var.set(e.src.NAME)
        self.autosave()
        if not visible:
            return
        warns = self.slot_warnings()
        for k, ui in self.slot_ui.items():
            try:
                ui["warn"].config(text="\n".join(warns.get(k, [])))
            except Exception:
                pass
        s = e.snap
        t = s.get("t") if s else None
        g = e.src.NAME
        if not t:
            self.game_lbl.config(text="%s: %s%s" % (g, translate("veri kaynağı bulunamadı", self.app.language), HINTS.get(g, "")))
        elif not s.get("valid", True):
            self.game_lbl.config(text="%s: %s" % (g, translate("veri yapısı uyuşmuyor!", self.app.language)))
        elif not s.get("live"):
            self.game_lbl.config(text="%s: %s" % (g, translate("bağlı, veri akmıyor (pist/pause?)", self.app.language)))
        else:
            self.game_lbl.config(text="%s: %s" % (g, translate("canlı veri", self.app.language)))

        if t and s.get("live"):
            self.bars["gas"]["value"] = t["gas"] * 100
            self.bars["brake"]["value"] = t["brake"] * 100
            self.bars["abs"]["value"] = min(1, t["abs"]) * 100
            self.bars["tc"]["value"] = min(1, t["tc"]) * 100
            sr = t["slipRatio"]
            self.val_lbl.config(text=(
                "Hız: %.0f km/h  Vites: %s\nKilit (ön): %.2f\nKayma (arka): %.2f\n"
                "ABS: %.2f  TC: %.2f  Devir: %%%.0f" % (t["speed"], t.get("gear", 0), -min(sr[0], sr[1]),
                                                       max(sr[2], sr[3]), t["abs"], t["tc"],
                                                       t.get("rpm_ratio", 0) * 100)))
        else:
            for b in self.bars.values():
                b["value"] = 0
            self.val_lbl.config(text="")
        c = self.app.theme.c
        try:
            self.canvas.configure(bg=c["bg"])
        except Exception:
            pass
        act = s.get("active", {}) if s else {}
        for k, lb in self.ind.items():
            lb.config(bg=c["accent"] if act.get(k) else c["ind_off"],
                      fg=c["on_accent"] if act.get(k) else c["muted"])
