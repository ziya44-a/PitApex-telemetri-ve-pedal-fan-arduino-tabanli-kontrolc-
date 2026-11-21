"""03 - LED Aydınlatma sayfası: MAX7219 8x8 LED matris (ve benzeri MAX7219 matrisleri).
LED kartı pedal/fan Arduino'sundan AYRI bir Arduino'ya bağlanır; bu sayfanın kendi port seçimi ve bağlantısı vardır."""
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, simpledialog

from core import led_matrix as M
from hardware.arduino import list_port_names

ROTATION_CHOICES = ["0°", "90°", "180°", "270°"]
NEUTRAL_LABELS = ["N harfi", "0 rakamı"]
NO_DATA_LABELS = ["Ekran boş kalsın", "Çizgi (-) göster"]
LEVEL_STYLE = {"ok": "Ok.TLabel", "warn": "Warn.TLabel", "bad": "Bad.TLabel"}

WIRING_NOTE = (
    "Donanım notları\n"
    "• LED kartı, pedal/fan Arduino'sundan AYRI bir Arduino'ya bağlanır (kendi USB portu). Arduino'ya "
    "firmware/LedMatrix/LedMatrix.ino yüklenir; Arduino IDE'de \"LedControl\" kütüphanesi gerekir.\n"
    "• Varsayılan bağlantı: MAX7219 VCC→5V, GND→GND, DIN→D12, CLK→D11, CS→D10 (kodun başındaki PIN_* satırlarıyla "
    "değiştirilir).\n"
    "• Modüllerin kablolaması farklı olabilir: harf yan ya da ters görünürse \"Yön testi\"ni kullanıp dönme ve "
    "ayna ayarını harf düzgün görünene kadar değiştir.\n"
    "• Parlaklığı düşük tutmak (2-6) hem gözü yormaz hem Arduino USB gücüyle daha güvenli çalışır; tüm LED'ler yanık "
    "ve parlaklık yüksekse modül yaklaşık 300 mA çekebilir.\n"
    "• PC kapanır ya da USB kopar ise LED kartı 3 saniye sonra ekranı kendiliğinden temizler."
)


class LedPage(ttk.Frame):
    def __init__(self, parent, app, preview_parent=None):
        super().__init__(parent)
        self.app = app
        self.preview_parent = preview_parent
        c = M.normalized(app.prefs.get("led", {}) or {})
        self.vars = {
            "enabled": tk.BooleanVar(value=c["enabled"]),
            "auto_connect": tk.BooleanVar(value=c["auto_connect"]),
            "brightness": tk.DoubleVar(value=c["brightness"]),
            "rotation": tk.StringVar(value=ROTATION_CHOICES[M.ROTATIONS.index(c["rotation"])]),
            "flip_h": tk.BooleanVar(value=c["flip_h"]),
            "flip_v": tk.BooleanVar(value=c["flip_v"]),
            "neutral": tk.StringVar(value=NEUTRAL_LABELS[M.NEUTRAL_CHOICES.index(c["gear"]["neutral"])]),
            "no_data": tk.StringVar(value=NO_DATA_LABELS[M.NO_DATA_CHOICES.index(c["gear"]["no_data"])]),
        }
        self.option_vars = {k: tk.BooleanVar(value=c[k]) for k in ("show_gear", "show_flags", "show_proximity", "show_adjustments")}
        self.adjust_vars = {k: tk.BooleanVar(value=v) for k,v in c["adjustment_enabled"].items()}
        self.adjust_seconds = tk.DoubleVar(value=c["adjustment_seconds"])
        self.flag_vars = {k: tk.BooleanVar(value=v) for k,v in c["flag_enabled"].items()}
        self.blink_vars = {k: tk.BooleanVar(value=c[k]) for k in ("blink_flags", "blink_proximity")}
        self.blink_speeds = {k: tk.IntVar(value=c[k]) for k in ("blink_flag_speed", "blink_proximity_speed")}
        self.custom_patterns = dict(c["custom_patterns"])
        self.colors = dict(c["colors"])
        self.preview_color = "gear"
        self._preview_test_until = 0.0
        self.port_var = tk.StringVar(value=c["port"])
        self.cfg = c
        self._last_saved = json.dumps(c, sort_keys=True)
        self._last_save_t = time.time()
        self._auto_done = False
        self.build()
        self.refresh_ports()

    # ---------------- arayüz ----------------
    def build(self):
        self.columnconfigure(0, weight=1)
        con = ttk.LabelFrame(self, text="LED kartı bağlantısı (ayrı Arduino)")
        con.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        self.port_box = ttk.Combobox(con, textvariable=self.port_var, width=34, state="readonly")
        self.port_box.grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(con, text="Yenile", command=self.refresh_ports).grid(row=0, column=1, padx=2)
        self.conn_btn = ttk.Button(con, text="Bağlan", command=self.toggle_conn)
        self.conn_btn.grid(row=0, column=2, padx=2)
        ttk.Checkbutton(con, text="Açılışta otomatik bağlan", variable=self.vars["auto_connect"]).grid(
            row=0, column=3, padx=12)
        self.status_lbl = ttk.Label(con, text="LED kartı bağlı değil", style="Muted.TLabel")
        self.status_lbl.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 6))

        mid = ttk.Frame(self)
        mid.grid(row=1, column=0, sticky="ew")
        mid.columnconfigure(0, weight=1)
        left = ttk.Frame(mid)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)

        feat = ttk.LabelFrame(left, text="Gösterilecek bilgi")
        feat.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        ttk.Checkbutton(feat, text="LED aydınlatma açık", variable=self.vars["enabled"]).grid(
            row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(feat, text="Özellik:").grid(row=0, column=1, padx=(24, 4))
        ttk.Combobox(feat, values=[n for _k, n in M.FEATURES], state="readonly", width=20).grid(row=0, column=2)
        feat.winfo_children()[-1].set(M.FEATURES[0][1])
        ttk.Label(feat, text="Vites verisi, pedal sayfasında seçili/algılanan oyundan gelir (R, N, 1-9; 10+ için '+').",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", padx=8)
        ttk.Label(feat, text="Boştayken (N) göster:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(feat, textvariable=self.vars["neutral"], values=NEUTRAL_LABELS, state="readonly",
                     width=14).grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(feat, text="Oyun verisi yokken:").grid(row=3, column=0, sticky="w", padx=8, pady=(0, 6))
        ttk.Combobox(feat, textvariable=self.vars["no_data"], values=NO_DATA_LABELS, state="readonly",
                     width=18).grid(row=3, column=1, columnspan=2, sticky="w", pady=(0, 6))

        options = ttk.LabelFrame(left, text="Bağımsız LED özellikleri ve renkler")
        options.grid(row=4, column=0, sticky="ew", padx=6, pady=4)
        for i,(key,title) in enumerate((("show_gear","Vites"),("show_flags","Yarış bayrakları"),("show_proximity","Yan araç uyarısı"))):
            ttk.Checkbutton(options, text=title, variable=self.option_vars[key]).grid(row=i,column=0,sticky="w",padx=8,pady=2)
        ttk.Label(options, text="Öncelik: yan araç > bayrak > vites. Renkler MAX7219 üzerinde değil, yalnızca önizlemede görünür.",
                  style="Muted.TLabel", wraplength=600).grid(row=3,column=0,columnspan=4,sticky="w",padx=8)
        # Equal-width grid: labels, color selectors and test buttons align vertically.
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=0)
        options.columnconfigure(2, weight=0)
        options.columnconfigure(3, weight=0)
        ttk.Separator(options, orient="horizontal").grid(row=4, column=0, columnspan=4, sticky="ew", pady=7)
        row = 5
        for key, name in M.FLAG_NAMES.items():
            ttk.Checkbutton(options, text=name, variable=self.flag_vars[key]).grid(
                row=row, column=0, sticky="w", padx=(10, 8), pady=3)
            ttk.Button(options, text="Renk", width=13,
                       command=lambda k=key: self.choose_color(k)).grid(row=row, column=1, sticky="ew", padx=5, pady=3)
            ttk.Button(options, text="Test", width=10,
                       command=lambda k=key: self.test_color(k, M.FLAG_PATTERNS[k])).grid(
                           row=row, column=2, sticky="ew", padx=5, pady=3)
            ttk.Button(options, text="Özelleştir", width=22,
                       command=lambda k=key: self.edit_pattern_key(k)).grid(row=row,column=3,sticky="ew",padx=(5,10),pady=3)
            row += 1
        ttk.Separator(options, orient="horizontal").grid(row=row, column=0, columnspan=4, sticky="ew", pady=7)
        row += 1
        for key, title in (("gear", "Vites"), ("left", "Sol araç"), ("right", "Sağ araç"), ("both", "İki tarafta araç"), ("rear", "Arkadan araç")):
            ttk.Label(options, text=title).grid(row=row, column=0, sticky="w", padx=(10, 8), pady=3)
            ttk.Button(options, text="Renk", width=13,
                       command=lambda k=key: self.choose_color(k)).grid(row=row, column=1, sticky="ew", padx=5, pady=3)
            ttk.Button(options, text="Test", width=10,
                       command=lambda k=key: self.test_color(k, M.proximity_pattern(k) if k != "gear" else M.glyph("1"))).grid(
                           row=row, column=2, sticky="ew", padx=5, pady=3)
            ttk.Button(options, text="Özelleştir", width=22,
                       command=lambda k=key: self.edit_pattern_key(k)).grid(row=row,column=3,sticky="ew",padx=(5,10),pady=3)
            row += 1

        adjust = ttk.LabelFrame(left, text="Araç ayarı değişiklikleri")
        adjust.grid(row=8, column=0, sticky="ew", padx=6, pady=5)
        ttk.Checkbutton(adjust, text="Değişiklikleri LED'de göster",
                        variable=self.option_vars["show_adjustments"]).grid(row=0,column=0,columnspan=3,sticky="w",padx=8,pady=4)
        for i,(key,label) in enumerate(M.ADJUSTMENTS.items(),start=1):
            ttk.Checkbutton(adjust,text=label,variable=self.adjust_vars[key]).grid(row=i,column=0,sticky="w",padx=8,pady=3)
            ttk.Button(adjust,text="Test",width=10,command=lambda k=key:self.test_adjustment(k)).grid(row=i,column=1,padx=8,pady=3)
            ttk.Button(adjust,text="Özelleştir",width=22,command=lambda k=key:self.edit_adjustment(k)).grid(row=i,column=2,padx=8,pady=3)
        ttk.Label(adjust,text="Gösterim süresi (sn)").grid(row=5,column=0,sticky="w",padx=8,pady=5)
        ttk.Spinbox(adjust,from_=0.5,to=8,increment=0.5,textvariable=self.adjust_seconds,width=7).grid(row=5,column=1,padx=8)
        ttk.Label(adjust,text="8×8 çözünürlük nedeniyle ayar adları gösterilmez; yalnızca yeni sayı gösterilir.",
                  style="Muted.TLabel").grid(row=6,column=0,columnspan=3,sticky="w",padx=8,pady=3)
        ttk.Label(adjust,text="Yeşil = değer artırıldı; kırmızı = değer azaltıldı (iyi/kötü anlamına gelmez).",
                  style="Muted.TLabel").grid(row=7,column=0,columnspan=3,sticky="w",padx=8,pady=3)
        ttk.Label(adjust,text="BB (Brake Bias) gösterilmez: 55.8 gibi ondalıklı değerler 8×8'de okunaklı değildir.",
                  style="Muted.TLabel").grid(row=8,column=0,columnspan=3,sticky="w",padx=8,pady=3)
        ttk.Label(adjust,text="Öncelik: yan araç > bayrak > değişen ayar > vites. Veri yoksa gösterilmez.",
                  style="Muted.TLabel").grid(row=9,column=0,columnspan=3,sticky="w",padx=8,pady=5)
        animation = ttk.LabelFrame(left, text="Animasyonlar")
        animation.grid(row=6, column=0, sticky="ew", padx=6, pady=5)
        for i, (enabled, speed, title) in enumerate((("blink_flags", "blink_flag_speed", "Yarış bayrakları"), ("blink_proximity", "blink_proximity_speed", "Yan araç"))):
            ttk.Checkbutton(animation, text=title + " - Yanıp sönsün", variable=self.blink_vars[enabled]).grid(row=i, column=0, sticky="w", padx=8, pady=5)
            ttk.Label(animation, text="Hız (1-10)").grid(row=i, column=1, padx=8)
            ttk.Spinbox(animation, from_=1, to=10, textvariable=self.blink_speeds[speed], width=5).grid(row=i, column=2, padx=6)
        reset_box = ttk.LabelFrame(left, text="Yalnızca LED ayarları")
        reset_box.grid(row=7, column=0, sticky="ew", padx=6, pady=5)
        ttk.Label(reset_box, text="Yalnızca LED ayarları silinir; tur kayıtları, pedal, fan ve diğer ayarlar korunur.", style="Muted.TLabel").pack(side="left", padx=8, pady=7)
        ttk.Button(reset_box, text="LED'i sıfırla", command=self.reset_led_only).pack(side="right", padx=8)

        editor = ttk.LabelFrame(left, text="LED piksel atama")
        editor.grid(row=5,column=0,sticky="ew",padx=6,pady=4)
        self.pattern_names = {**{"gear_"+str(n):"Gear "+str(n) for n in range(1,10)},
                              **{"gear_N":"Neutral N","gear_R":"Reverse R","gear_+":"Gear 10+","gear_-":"No data (-)","left":"Car left","right":"Car right","both":"Cars both","rear":"Car behind"},
                              **{k:"Flag: "+v for k,v in M.FLAG_NAMES.items()}}
        self.pattern_var = tk.StringVar(value="Gear 1")
        ttk.Combobox(editor,textvariable=self.pattern_var,values=list(self.pattern_names.values()),state="readonly",width=24).pack(side="left",padx=6,pady=5)
        ttk.Button(editor,text="Edit 8×8",command=self.edit_pattern).pack(side="left",padx=4)
        ttk.Button(editor,text="Test",command=self.test_pattern).pack(side="left",padx=4)
        disp = ttk.LabelFrame(left, text="Ekran ayarları")
        disp.grid(row=1, column=0, sticky="ew", padx=6, pady=4)
        ttk.Label(disp, text="Parlaklık (0-15)").grid(row=0, column=0, sticky="w", padx=8)

        def snap(v):
            self.vars["brightness"].set(int(round(float(v))))
        ttk.Scale(disp, from_=0, to=M.BRIGHTNESS_MAX, variable=self.vars["brightness"], length=200,
                  command=snap).grid(row=0, column=1, padx=4)
        ttk.Spinbox(disp, from_=0, to=M.BRIGHTNESS_MAX, textvariable=self.vars["brightness"], width=5).grid(
            row=0, column=2, padx=4, pady=3)
        ttk.Label(disp, text="Dönme (saat yönü)").grid(row=1, column=0, sticky="w", padx=8)
        ttk.Combobox(disp, textvariable=self.vars["rotation"], values=ROTATION_CHOICES, state="readonly",
                     width=8).grid(row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Checkbutton(disp, text="Yatay ayna", variable=self.vars["flip_h"]).grid(row=2, column=0, sticky="w", padx=8)
        ttk.Checkbutton(disp, text="Dikey ayna", variable=self.vars["flip_v"]).grid(row=2, column=1, sticky="w", padx=4)

        tst = ttk.LabelFrame(left, text="Test (oyun gerekmez)")
        tst.grid(row=2, column=0, sticky="ew", padx=6, pady=4)
        ttk.Button(tst, text="Yön testi (R)", command=lambda: self.test(M.glyph("R"))).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(tst, text="Tüm LED'ler açık", command=lambda: self.test(M.all_on())).grid(row=0, column=1, padx=4)
        ttk.Button(tst, text="Durdur", command=self.app.led.stop_test).grid(row=0, column=2, padx=4)
        ttk.Label(tst, text="Testler 4 saniye sürer. Harf düzgün okunuyorsa yön doğrudur.", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 6))

        prev = ttk.LabelFrame(self.preview_parent if self.preview_parent is not None else mid, text="Önizleme")
        if self.preview_parent is not None:
            prev.pack(anchor="n", fill="x")
        else:
            prev.grid(row=0, column=1, sticky="n", padx=6, pady=4)
        self.canvas = tk.Canvas(prev, width=176, height=176, highlightthickness=0, bg=self.app.theme.c["panel"])
        self.canvas.grid(row=0, column=0, padx=10, pady=(10, 4))
        self.prev_lbl = ttk.Label(prev, text="", style="Muted.TLabel")
        self.prev_lbl.grid(row=1, column=0, pady=(0, 8))

        ttk.Label(self, text=WIRING_NOTE, style="Muted.TLabel", justify="left", wraplength=900).grid(
            row=2, column=0, sticky="w", padx=10, pady=(6, 8))

    def selected_pattern(self):
        return next((k for k,v in self.pattern_names.items() if v==self.pattern_var.get()),"gear_1")

    def pattern_rows(self,key):
        if key.startswith("gear_"): base=M.glyph(key[5:])
        elif key.startswith("adjust_"):
            _, kind, number = key.split("_")
            base=M.adjustment_image(kind,int(number))
        elif key in M.FLAG_PATTERNS: base=M.FLAG_PATTERNS[key]
        elif key=="both": base=tuple(a|b for a,b in zip(M.proximity_pattern("left"),M.proximity_pattern("right")))
        else: base=M.proximity_pattern(key)
        return tuple(self.custom_patterns.get(key,base))

    def test_pattern(self):
        key=self.selected_pattern()
        self.preview_color=key if key in self.colors else "gear"
        self.test(self.pattern_rows(key))

    def edit_pattern_key(self, key):
        if key == "gear":
            value = simpledialog.askstring("LED", "Vites (1-9, N, R, +, -):", parent=self, initialvalue="1")
            if value is None: return
            value = value.strip().upper()
            if value not in [str(i) for i in range(1,10)] + ["N", "R", "+", "-"]:
                messagebox.showwarning("PitApex", "Geçersiz vites / Invalid gear", parent=self)
                return
            key = "gear_" + value
        self.pattern_var.set(self.pattern_names.get(key, key))
        self.edit_pattern()

    def edit_adjustment(self, key):
        value = simpledialog.askinteger("LED", "Özelleştirilecek değer (0–99):", parent=self, minvalue=0, maxvalue=99, initialvalue=4)
        if value is None:
            return
        pattern_key = "adjust_%s_%d" % (key, value)
        self.pattern_names[pattern_key] = "%s: %d" % (M.ADJUSTMENTS[key], value)
        self.edit_pattern_key(pattern_key)

    def edit_pattern(self):
        key=self.selected_pattern()
        win=tk.Toplevel(self);win.title("LED Pixel Editor — "+self.pattern_names[key]);win.resizable(False,False)
        rows=self.pattern_rows(key)
        bits=[[(rows[r]>>(7-c))&1 for c in range(8)] for r in range(8)]
        cells=[];board=tk.Frame(win,padx=12,pady=12);board.pack()
        def paint():
            for r in range(8):
                for c in range(8): cells[r][c].config(bg="#ffb000" if bits[r][c] else "#303030")
        def toggle(r,c):
            bits[r][c]^=1;paint()
        for r in range(8):
            line=[]
            for c in range(8):
                b=tk.Button(board,width=3,height=1,command=lambda r=r,c=c:toggle(r,c),relief="flat")
                b.grid(row=r,column=c,padx=2,pady=2);line.append(b)
            cells.append(line)
        paint()
        ttk.Label(win,text="Click each pixel to toggle / Her LED'e tıklayarak değiştir").pack()
        def set_all(value):
            for r in range(8):
                for c in range(8): bits[r][c]=value
            paint()
        def restore():
            self.custom_patterns.pop(key,None);self.sync();win.destroy()
        def save():
            self.custom_patterns[key]=[sum(bits[r][c]<<(7-c) for c in range(8)) for r in range(8)]
            self.sync();win.destroy()
        actions=ttk.Frame(win);actions.pack(padx=8,pady=10)
        for name,cmd in (("All on",lambda:set_all(1)),("Clear",lambda:set_all(0)),("Default",restore),("Save",save)):
            ttk.Button(actions,text=name,command=cmd).pack(side="left",padx=3)

    def choose_color(self, key):
        color = colorchooser.askcolor(color=self.colors[key], title="LED önizleme rengi: " + key)[1]
        if color:
            self.colors[key] = color
            self.preview_color = key
            self.sync()

    def test_adjustment(self, key):
        self.preview_color = "gear"
        self.test(self.custom_patterns.get("adjust_%s_4" % key, M.adjustment_image(key, 4)))

    def test_color(self, key, rows):
        self.preview_color = key
        self.test(rows)

    # ---------------- bağlantı ----------------
    def refresh_ports(self):
        names = list_port_names()
        self.port_box["values"] = names
        saved = self.vars_port()
        match = next((n for n in names if saved and n.split(" ")[0] == saved), None)
        if match:
            self.port_var.set(match)

    def vars_port(self):
        v = self.port_var.get()
        return v.split(" ")[0] if v else ""

    def main_port(self):
        try:
            return (self.app.port_var.get() or "").split(" ")[0] if self.app.link.connected else ""
        except Exception:
            return ""

    def toggle_conn(self):
        link = self.app.led_link
        if link.connected:
            link.disconnect()
            self.conn_btn.config(text="Bağlan")
            return
        port = self.vars_port()
        if not port:
            messagebox.showinfo("PitApex", "Önce LED kartının portunu seç.")
            return
        if port == self.main_port():
            messagebox.showerror("PitApex", "Bu port pedal/fan Arduino'suna bağlı. LED kartı için ayrı bir port seç.")
            return
        self.connect(port)

    def connect(self, port):
        try:
            self.app.led_link.connect(port)
            self.conn_btn.config(text="Kes")
            self.cfg = dict(self.cfg, port=port)
        except Exception as e:
            messagebox.showerror("PitApex", "Bağlanılamadı:\n%s\n\nArduino IDE Serial Monitor açıksa kapat." % e)

    def test(self, rows):
        self.app.led.start_test(rows, 4.0)

    # ---------------- ayar eşitleme ----------------
    def sync(self):
        raw = {}
        for k, var in self.vars.items():
            try:
                raw[k] = var.get()
            except Exception:
                raw[k] = None                      # kutu geçici boşsa varsayılan/eski değer
        old = self.cfg
        rot = raw.get("rotation")
        gear = {"neutral": M.NEUTRAL_CHOICES[NEUTRAL_LABELS.index(raw["neutral"])] if raw.get("neutral") in NEUTRAL_LABELS
                else old["gear"]["neutral"],
                "no_data": M.NO_DATA_CHOICES[NO_DATA_LABELS.index(raw["no_data"])] if raw.get("no_data") in NO_DATA_LABELS
                else old["gear"]["no_data"]}
        port = self.app.led_link.ser.port if self.app.led_link.connected and hasattr(self.app.led_link.ser, "port") \
            else (self.vars_port() or old["port"])
        self.cfg = M.normalized({
            "enabled": raw.get("enabled", old["enabled"]),
            "auto_connect": raw.get("auto_connect", old["auto_connect"]),
            "brightness": raw["brightness"] if raw.get("brightness") is not None else old["brightness"],
            "rotation": int(rot[:-1]) if rot in ROTATION_CHOICES else old["rotation"],
            "flip_h": raw.get("flip_h", old["flip_h"]), "flip_v": raw.get("flip_v", old["flip_v"]),
            "feature": "gear", "gear": gear, "port": port,
            **{k:v.get() for k,v in self.option_vars.items()},
            "flag_enabled": {k:v.get() for k,v in self.flag_vars.items()},
            **{k:v.get() for k,v in self.blink_vars.items()},
            **{k:v.get() for k,v in self.blink_speeds.items()},
            "adjustment_enabled": {k:v.get() for k,v in self.adjust_vars.items()},
            "adjustment_seconds": self.adjust_seconds.get(),
            "custom_patterns": self.custom_patterns, "colors": self.colors})

    def get_cfg(self):
        return self.cfg

    def autosave(self):
        if time.time() - self._last_save_t < 3:
            return
        self._last_save_t = time.time()
        snap = json.dumps(self.cfg, sort_keys=True)
        if snap != self._last_saved:
            self.app.prefs.set("led", self.cfg)
            self._last_saved = snap

    def load_prefs(self, raw):
        c = M.normalized(raw or {})
        self.apply(c)
        self._last_saved = json.dumps(self.cfg, sort_keys=True)

    def apply(self, c):
        self.vars["enabled"].set(c["enabled"])
        self.vars["auto_connect"].set(c["auto_connect"])
        self.vars["brightness"].set(c["brightness"])
        self.vars["rotation"].set(ROTATION_CHOICES[M.ROTATIONS.index(c["rotation"])])
        self.vars["flip_h"].set(c["flip_h"])
        self.vars["flip_v"].set(c["flip_v"])
        self.vars["neutral"].set(NEUTRAL_LABELS[M.NEUTRAL_CHOICES.index(c["gear"]["neutral"])])
        self.vars["no_data"].set(NO_DATA_LABELS[M.NO_DATA_CHOICES.index(c["gear"]["no_data"])])
        for k,v in self.option_vars.items(): v.set(c[k])
        for k,v in self.flag_vars.items(): v.set(c["flag_enabled"][k])
        for k,v in self.blink_vars.items(): v.set(c[k])
        for k,v in self.blink_speeds.items(): v.set(c[k])
        for k,v in self.adjust_vars.items(): v.set(c["adjustment_enabled"][k])
        self.adjust_seconds.set(c["adjustment_seconds"])
        self.custom_patterns = dict(c["custom_patterns"])
        self.colors = dict(c["colors"])
        self.cfg = c

    def reset_led_only(self):
        if not messagebox.askyesno("Reset LED / LED sıfırlama", "Yalnızca LED ayarları varsayılana döndürülsün mü?\nReset ONLY LED settings?", parent=self):
            return
        self.app.led.stop_test()
        self.apply(M.normalized({}))
        self.port_var.set("")
        self.preview_color = "gear"
        self.app.prefs.set("led", self.cfg)
        self._last_saved = json.dumps(self.cfg, sort_keys=True)
        self._last_save_t = time.time()
        self.draw_preview(M.BLANK)

    def reset_after_wipe(self):
        self.apply(M.normalized({}))
        self.port_var.set("")
        self._last_saved = json.dumps(self.cfg, sort_keys=True)     # temizlenen veri kendiliğinden geri yazılmasın

    # ---------------- görsel güncelleme ----------------
    def tick(self, visible):
        self.sync()
        self.autosave()
        if not self._auto_done:
            self._auto_done = True
            if self.cfg["auto_connect"] and self.cfg["port"] and not self.app.led_link.connected \
                    and self.cfg["port"] != self.main_port():
                try:
                    self.connect(self.cfg["port"])
                except Exception:
                    pass
        if not visible:
            return
        s = self.app.led.status
        self.status_lbl.config(text=s["text"], style=LEVEL_STYLE.get(s["level"], "Muted.TLabel"))
        self.conn_btn.config(text="Kes" if self.app.led_link.connected else "Bağlan")
        info = s["info"]
        if info.startswith("Bayrak: "):
            self.preview_color = next((k for k,v in M.FLAG_NAMES.items() if v == info[8:]), "gear")
        elif info.startswith("Yan araç: "):
            self.preview_color = "rear" if info.endswith("rear") else ("right" if info.endswith("right") else ("both" if info.endswith("both") else "left"))
        elif info.startswith("Ayar: "):
            self.preview_color = "adjust_up" if info.endswith("(up)") else "adjust_down"
        elif info.startswith("Vites:"):
            self.preview_color = "gear"
        self.draw_preview(s["rows"])
        self.prev_lbl.config(text=s["info"])

    def draw_preview(self, rows):
        cv, c = self.canvas, self.app.theme.c
        cv.configure(bg=c["panel"])
        cv.delete("all")
        step = 21
        for r in range(8):
            for col in range(8):
                on = (rows[r] >> (7 - col)) & 1
                x, y = 4 + col * step, 4 + r * step
                flag = self.preview_color
                if flag in M.FLAG_NAMES and (info_flag := flag) and (on or flag in ("double_yellow", "final", "warning", "mechanical", "checkered")):
                    color = M.flag_preview_color(info_flag, r, col, self.colors)
                else:
                    color = ({"adjust_up":"#00e676", "adjust_down":"#ff3030"}.get(flag, self.colors.get(flag,"#ff3b30"))) if on else c["border"]
                cv.create_oval(x, y, x + step - 4, y + step - 4, fill=color, outline="")
