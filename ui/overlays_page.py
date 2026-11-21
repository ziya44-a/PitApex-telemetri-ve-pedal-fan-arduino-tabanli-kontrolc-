"""Birden fazla bağımsız, üstte kalan telemetri overlay'inin yönetimi."""
import tkinter as tk
import time
import re
import os
import sys
from collections import deque
from tkinter import ttk

from core.models import gear_text, fmt_ms
from ui.i18n import translate
from ui import tyre_temp
from ui.car_view import CarAssets, GREEN, NEUTRAL, RED, STEPS, draw_car, summary_text, wheel_levels, color_of, level_color, wheel_warning, pull_banner, kpa_to_psi

OVERLAYS = {
    "speed": ("Hız göstergesi", "Hız"),
    "pedals": ("Pedal göstergesi", "Gaz / Fren"),
    "rpm": ("Devir ve vites", "RPM / Vites"),
    "lap": ("Tur bilgisi", "Tur"),
    "tyres": ("Araç Durumu", "Üstten araç, lastikler ve desteklenen hasar verileri"),
    "parts": ("Parça Durumu", "Desteklenen mekanik durum verileri"),
}


# Arka plan penceresinin rengi. On plan penceresinde "saydam anahtar" rengi olarak AYNI renk kullanilir:
# anahtar renkli pikseller delinip arkadaki yari saydam pencere gorunur; yazi/cizgi kenarlarindaki
# yumusatma pikselleri ise anahtara degil bu koyu renge karisir (eski macenta anahtarda pembe halka olusuyordu).
# On planda bu rengin kendisiyle dolgu/yazi YAZILMAMALI (delinir).
BACKDROP_COLOR = "#151515"
TRANSPARENT_KEY = BACKDROP_COLOR
OPAQUE_CANVAS = "#12161d"      # saydamlik kapaliyken (tek opak pencere) tuval zemini
OPAQUE_LABEL = "#171a20"
MAX_TRANSPARENCY = 90          # %90'da durur: pencere tamamen kaybolup bulunamaz hale gelmesin


class OverlayWindow:
    def __init__(self, manager, key, geometry=None):
        self.manager, self.key = manager, key
        self.root = manager.app.root
        self.win = tk.Toplevel(self.root)
        self.win.title("PitApex · " + translate(OVERLAYS[key][0], getattr(manager.app, "language", "tr")))
        self.background = None
        self._background_supported = False
        self._focus_bound = False
        self._last_sig = None
        self._resize_redraw_id = None
        self._vehicle_frame = None
        self._geom = geometry or manager.default_geometry(key)
        self.win.configure(bg=BACKDROP_COLOR)
        self.win.attributes("-topmost", True)
        self.win.overrideredirect(True)
        self.win.geometry(self._geom)
        self.win.bind("<ButtonPress-1>", self._drag_start)
        self.win.bind("<B1-Motion>", self._drag)
        self.win.bind("<Button-3>", lambda _e: manager.close(key))
        self.label = tk.Label(self.win, text="Veri bekleniyor", bg=OPAQUE_LABEL, fg="#f2f2f2",
                              font=("Segoe UI", 19, "bold"), padx=14, pady=9, justify="center")
        self.label.pack(fill="both", expand=True)
        self.label.bind("<ButtonPress-1>", self._drag_start)
        self.label.bind("<B1-Motion>", self._drag)
        self.label.bind("<ButtonRelease-1>", lambda _e: self.manager.save_window(self.key))
        self.history = deque()
        self.canvas = None
        if key in ("pedals", "tyres", "parts"):
            self.label.pack_forget()
            self.canvas = tk.Canvas(self.win, bg=OPAQUE_CANVAS, highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            self.canvas.bind("<Configure>", self._schedule_resize_redraw)
            self.canvas.bind("<ButtonPress-1>", self._drag_start)
            self.canvas.bind("<B1-Motion>", self._drag)
            self.canvas.bind("<ButtonRelease-1>", lambda _e: self.manager.save_window(self.key))
        # Frameless windows have no native resize border; provide a mouse-operated
        # corner grip on every overlay, including the transparent pedal canvas.
        self.grip = tk.Label(self.win, text="◢", font=("Segoe UI Symbol", 7),
                             fg="#b9c2ce", bg="#343a45", cursor="size_nw_se", padx=0)
        self.grip.place(relx=1, rely=1, anchor="se")
        self.grip.bind("<ButtonPress-1>", self._resize_start)
        self.grip.bind("<B1-Motion>", self._resize_drag)
        self.grip.bind("<ButtonRelease-1>", lambda _e: self.manager.save_window(self.key))
        # Saydam modda bos alanlar tiklamayi oyuna gecirir; pencereyi tasimak icin her zaman tutulabilir
        # kucuk opak bir tutamac (sag ust).
        self.handle = tk.Label(self.win, text="≡", font=("Segoe UI", 9, "bold"), fg="#b9c2ce", bg="#343a45",
                               cursor="fleur", padx=5)
        self.handle.bind("<ButtonPress-1>", self._drag_start)
        self.handle.bind("<B1-Motion>", self._drag)
        self.handle.bind("<ButtonRelease-1>", lambda _e: self.manager.save_window(self.key))
        self.handle.bind("<Button-3>", lambda _e: manager.close(key))
        self.win.bind("<Configure>", self._geometry_changed)
        self.win.bind("<ButtonRelease-1>", lambda _e: self.manager.save_window(self.key))
        self._x = self._y = 0
        self.win.protocol("WM_DELETE_WINDOW", lambda: manager.close(key))
        self.apply_opacity()

    # ---- arka plan (saydamlik) ----
    def _wants_backdrop(self):
        """Saydamlik icin arka plan penceresi gerekir (Windows). Pedal overlay'i, saydamlik %0 iken eski
        tek-opak-pencere yolunu aynen korur; yalnizca kullanici saydamligi arttirinca arka plan acilir."""
        if sys.platform != "win32":
            return False
        return self.key != "pedals" or self.manager.opacity_of(self.key) < 100

    def _current_geometry(self):
        try:
            g = self.win.geometry()
        except tk.TclError:
            g = ""
        return self._geom if (not g or g.startswith("1x1")) else g

    def _enable_backdrop(self):
        bg = None
        try:
            bg = tk.Toplevel(self.root)
            bg.overrideredirect(True)
            bg.configure(bg=BACKDROP_COLOR)
            bg.attributes("-topmost", True)
            bg.geometry(self._current_geometry())
            self.win.configure(bg=TRANSPARENT_KEY)
            self.win.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            if bg is not None:
                try:
                    bg.destroy()
                except tk.TclError:
                    pass
            return False
        self.background = bg
        self._background_supported = True
        bg.bind("<ButtonPress-1>", self._drag_start)
        bg.bind("<B1-Motion>", self._drag)
        bg.bind("<ButtonRelease-1>", lambda _e: self.manager.save_window(self.key))
        self._make_backdrop_clickthrough()
        self._ensure_backdrop_behind()
        if not self._focus_bound:
            self.win.bind("<FocusIn>", self._on_focus, add="+")
            self.win.bind("<ButtonPress-1>", self._on_focus, add="+")
            self._focus_bound = True
        return True

    def _disable_backdrop(self):
        bg, self.background = self.background, None
        self._background_supported = False
        if bg is not None:
            try:
                bg.destroy()
            except tk.TclError:
                pass
        try:
            self.win.attributes("-transparentcolor", "")
            self.win.configure(bg=BACKDROP_COLOR)
        except tk.TclError:
            pass

    def _label_bg(self):
        return TRANSPARENT_KEY if self._background_supported else OPAQUE_LABEL

    def _apply_foreground(self):
        """On plan renkleri: saydam modda zemin 'anahtar' renk (delinir), degilse eski opak renkler."""
        if self.canvas is not None:
            self.canvas.configure(bg=TRANSPARENT_KEY if self._background_supported else OPAQUE_CANVAS)
        self.label.configure(bg=self._label_bg())
        if self._background_supported:
            self.handle.place(relx=1, x=-2, y=2, anchor="ne")
            self.handle.lift()
        else:
            self.handle.place_forget()
        self._last_sig = None

    def _make_backdrop_clickthrough(self):
        """Windows backdrop must not steal focus or mouse events from the overlay."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = wintypes.HWND(self.background.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x20
            WS_EX_NOACTIVATE = 0x08000000
            get_style = user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.GetWindowLongW
            set_style = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
            get_style.argtypes = [wintypes.HWND, ctypes.c_int]
            get_style.restype = ctypes.c_ssize_t
            set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            set_style.restype = ctypes.c_ssize_t
            current = get_style(hwnd, GWL_EXSTYLE)
            set_style(hwnd, GWL_EXSTYLE, current | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
        except (AttributeError, OSError, ValueError):
            pass

    def _ensure_backdrop_behind(self):
        if not self._background_supported:
            return
        try:
            self.background.lower(self.win)
            self.win.lift()
        except tk.TclError:
            pass

    def _on_focus(self, _event=None):
        self._ensure_backdrop_behind()

    def apply_opacity(self):
        """Arka plan saydamligi: opacity = arka planin GORUNURLUGU (%10-100). Saydamlik = 100 - opacity.
        Yazilar/gostergeler (on plan) hicbir zaman soldurulmaz."""
        alpha = max(.1, min(1., self.manager.opacity_of(self.key) / 100.))
        want = self._wants_backdrop()
        if want and not self._background_supported:
            self._enable_backdrop()
        elif not want and self._background_supported:
            self._disable_backdrop()
        if self._background_supported:
            try:
                self.background.attributes("-alpha", alpha)
            except tk.TclError:
                pass
            self._sync_background()
        else:
            # Tek opak pencere: Windows'ta katmanli pencere cakismalarini onler.
            try:
                self.win.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
        self._apply_foreground()
        self._redraw()

    def _sync_background(self):
        if not self._background_supported:
            return
        try:
            self.background.geometry(self.win.geometry())
            # Do not raise either window on every geometry event: doing so can
            # create a focus/stacking loop that makes the backdrop appear black.
        except tk.TclError:
            pass

    def _geometry_changed(self, event):
        if event.widget == self.win:
            self._sync_background()
        if event.widget == self.win and self.canvas is not None:
            self._schedule_resize_redraw()

    def _schedule_resize_redraw(self, _event=None):
        """Coalesce rapid Windows Configure events while dragging window borders."""
        if self._resize_redraw_id is not None:
            try:
                self.win.after_cancel(self._resize_redraw_id)
            except tk.TclError:
                pass
        try:
            self._resize_redraw_id = self.win.after(55, self._finish_resize_redraw)
        except tk.TclError:
            self._resize_redraw_id = None

    def _finish_resize_redraw(self):
        self._resize_redraw_id = None
        self._redraw()

    def _draw_pedals(self, gas, brake):
        if self.canvas is None:
            return
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 90)
        pad, title_h, foot_h = 9, 20, 27
        top, bottom = title_h, max(title_h+25, h-foot_h)
        bar_w = max(14, min(32, int(w*.055)))
        gap = max(7, int(w*.018))
        bx = w-pad-2*bar_w-gap
        gx = bx+bar_w+gap
        graph_l, graph_r = pad, max(pad+30, bx-gap)
        # Solid text backing prevents Windows chroma-key from eating antialiased glyph edges.
        c.create_rectangle(pad-3, 1, min(w-4, pad+131), 18, fill="#20252c", outline="")
        c.create_text(pad, 9, anchor="w", text="PITAPEX · PEDALS", fill="#ffffff", font=("Segoe UI", 9, "bold"))
        for i in range(5):
            y = top+(bottom-top)*i/4
            c.create_line(graph_l,y,graph_r,y,fill="#3b444f",dash=(3,4))
        now = time.monotonic()
        duration = self.manager.history_seconds.get(self.key, 5)
        samples = [(t,g,b) for t,g,b in self.history if t >= now-duration]
        for index,color in ((1,"#39d879"),(2,"#fa4848")):
            coords = []
            for t,g,b in samples:
                value = (g,b)[index-1]
                if value is not None:
                    coords.extend((graph_r-(now-t)/duration*(graph_r-graph_l), bottom-value*(bottom-top)))
            if len(coords)>=4:
                c.create_line(*coords, fill=color, width=2, smooth=False)
        for x,value,color,label in ((bx,brake,"#fa4848","FREN"),(gx,gas,"#39d879","GAZ")):
            c.create_rectangle(x,top,x+bar_w,bottom,fill="#343a45",outline="")
            if value is not None:
                c.create_rectangle(x,bottom-value*(bottom-top),x+bar_w,bottom,fill=color,outline="")
            # Opaque text-only strip keeps the percentage and caption crisp.
            c.create_rectangle(x-5, bottom+2, x+bar_w+5, bottom+27, fill="#20252c", outline="")
            c.create_text(x+bar_w/2,bottom+10,text="—" if value is None else f"{round(value*100)}%",fill=color,font=("Segoe UI",8,"bold"))
            c.create_text(x+bar_w/2,bottom+22,text=label,fill="#f2f2f2",font=("Segoe UI",7,"bold"))

    def _redraw(self):
        if self.key == "pedals":
            self._draw_pedals(None, None)
        elif self.key in ("tyres", "parts"):
            self._draw_vehicle()

    def _vehicle_signature(self):
        f = self._vehicle_frame
        names = ("tyre_temp_c", "tyre_press_kpa", "tyre_wet", "fuel_l", "body_damage", "wheel_damage", "engine_damage",
                 "gearbox_damage", "aero_damage", "suspension_damage", "steering_damage", "brake_damage",
                 "cooling_damage")
        vals = tuple(repr(getattr(f, n, None)) for n in names) if f is not None else None
        return (self.key, self.canvas.winfo_width(), self.canvas.winfo_height(), self._background_supported,
                f is not None, vals, repr(self.manager.tyre_cfg))

    def _draw_vehicle_fallback_car(self, c, sx, sy, rect, line, txt, poly):
        """Gorsel dosyalari yoksa/acilamazsa: eski elle cizilmis poligon arac (arac her zaman cizilir)."""
        # Front is at the TOP; the rear wing and PitApex wordmark at BOTTOM.
        # Shadow, four wheels and the characteristic wide GT body.
        rect(293,95,467,574,fill="#0a0c0f")
        for xx in (286,450):
            for yy in (160,438):
                rect(xx,yy,xx+24,yy+90,fill="#090b0e",outline="#555e68")
                for t in range(yy+13,yy+86,15):
                    line(xx+4,t,xx+20,t,"#343b44")
        poly([(348,105),(412,105),(448,126),(458,190),(450,251),
              (455,430),(449,509),(422,545),(338,545),(311,509),
              (305,430),(310,251),(302,190),(312,126)],"#343940","#89919a",2)
        poly([(347,114),(413,114),(433,145),(431,224),(329,224),(327,145)],"#242a31")
        poly([(331,232),(429,232),(440,300),(430,376),(330,376),(320,300)],"#161c24")
        poly([(335,239),(425,239),(434,298),(326,298)],"#0a111a","#56616c")
        poly([(330,386),(430,386),(435,492),(325,492)],"#242930")
        for xx in (337,353,369,385,401,417):
            line(xx,406,xx,468,"#11161d",2)
        # Headlights and hood vents.
        for x1,x2 in ((318,343),(417,442)):
            poly([(x1,137),(x2,130),(x2-3,165),(x1+4,174)],"#d5e8f1","#6e8798")
        for x1 in (335,402):
            for yy in (181,194,207):
                line(x1,yy,x1+23,yy+5,"#090c10",3)
        # Door contours, mirror housings and subtle orange accents.
        for xx in (315,445):
            line(xx,255,xx,409,"#c0783e",2)
        rect(293,283,310,300,fill="#434b54",outline="#7c8793")
        rect(450,283,467,300,fill="#434b54",outline="#7c8793")
        for xx in (320,440):
            line(xx,419,xx,489,"#b36931",2)
        # Rear wing is BELOW the car.
        rect(286,535,474,565,fill="#11151b",outline="#9aa3ad")
        rect(282,533,289,568,fill="#6d7782")
        rect(471,533,478,568,fill="#6d7782")
        txt(380,550,"PitApex",22,"#c47b42",anchor="center",bold=True)

    def _draw_vehicle(self):
        """Arac/parca HUD'u. Eksik telemetri 'Veri yok' olarak gosterilir; hasar yalnizca oyunun gercek
        hasar degerinden boyanir (kirmizi=hasarli, yesil=saglam, veri yoksa boyanmaz)."""
        c = self.canvas
        if c is None:
            return
        sig = self._vehicle_signature()
        if sig == self._last_sig:
            return
        self._last_sig = sig
        c.delete("all")
        supported = self._background_supported
        panel = "" if supported else "#171b21"       # saydam modda kartlarin ici de saydam
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 90)
        bw, bh = (760, 650) if self.key == "tyres" else (520, 650)
        sx, sy = w / bw, h / bh
        def rect(x1,y1,x2,y2,fill="#171a20",outline="",width=1):
            return c.create_rectangle(x1*sx,y1*sy,x2*sx,y2*sy,fill=fill,outline=outline,width=width)
        def line(x1,y1,x2,y2,color="#505862",width=1):
            return c.create_line(x1*sx,y1*sy,x2*sx,y2*sy,fill=color,width=width)
        def txt(x,y,value,size=12,color="#e8ebef",anchor="w",bold=False):
            return c.create_text(x*sx,y*sy,text=str(value),fill=color,anchor=anchor,
                                 font=("Segoe UI",max(7,round(size*min(sx,sy))),"bold" if bold else "normal"))
        if not supported:
            rect(0,0,bw,bh,fill="#101318")
        txt(22,28,"PitApex",20,"#ff9d2e",bold=True)
        txt(135,28,"/  ARAÇ DURUMU" if self.key=="tyres" else "/  PARÇA DURUMU",17,bold=True)
        line(20,55,bw-20,55)
        frame = self._vehicle_frame
        tcfg = self.manager.tyre_cfg
        twet = getattr(frame,"tyre_wet",None) if frame is not None else None
        tname, _tauto, _tknown = tyre_temp.resolve_profile(tcfg, twet)
        trange = tcfg["ranges"][tname]
        if self.key=="tyres":
            txt(22,46,tyre_temp.profile_label(tcfg, twet),9,"#aab4c1")
        def read(name):
            return getattr(frame,name,None) if frame is not None else None
        def fmt(value,unit="",precision=0):
            try:
                if value is None: return "—"
                return f"{float(value):.{precision}f}{unit}"
            except (ValueError,TypeError): return "—"
        def card(x,y,width,height):
            rect(x,y,x+width,y+height,fill=panel,outline="#3a424d")
        if self.key=="parts":
            rows=[("Motor","engine_damage"),("Şanzıman","gearbox_damage"),
                  ("Aerodinamik","aero_damage"),("Süspansiyon","suspension_damage"),
                  ("Direksiyon","steering_damage"),("Frenler","brake_damage"),
                  ("Soğutma","cooling_damage")]
            card(20,83,480,440)
            for i,(label,field) in enumerate(rows):
                y=118+i*57
                raw=read(field)
                txt(40,y,label,16,bold=True)
                if raw is None:
                    txt(475,y,"Veri yok",13,"#8e9aaa",anchor="e")
                    rect(275,y+11,470,y+18,fill="#323942")
                else:
                    # Damage telemetry is not assumed to be a 0–100 health percentage.
                    txt(475,y,fmt(raw),13,"#d3dae2",anchor="e")
                    rect(275,y+11,470,y+18,fill="#323942")
                if i<6: line(40,y+29,480,y+29,"#2b323b")
            card(20,544,480,83)
            txt(38,566,"AERODİNAMİK HASAR",14,"#ff9d2e",bold=True)
            txt(38,600,"Ön / arka kanat: oyun verisi varsa gösterilir",12,"#aab4c1")
            return

        # ---- Araç Durumu: üstten araç görseli + hasar boyaması ----
        body, wheelsd = read("body_damage"), read("wheel_damage")
        wstate0 = wheel_levels(wheelsd)
        banner=pull_banner(wstate0)
        if banner: txt(285,27,"⚠ "+banner,10,RED,bold=True)
        txt(490,27,"Sağlam",10,"#aab4c1")                       # gösterge: yeşil -> kırmızı geçiş çubuğu
        for k in range(STEPS):
            rect(530+k*6,20,530+k*6+6,32,fill=level_color(k))
        txt(530+STEPS*6+5,27,"Kırık",10,"#aab4c1")
        rect(630,20,642,32,fill=NEUTRAL)
        txt(647,27,"Veri yok",10,"#aab4c1")
        drawn = None
        assets = self.manager.car_assets()
        if assets is not None:
            max_h = min(500*sy, 340*sx/assets.aspect)
            drawn = draw_car(c, assets, 380*sx, 70*sy, max_h, body, wheelsd)
        if drawn is None:
            self._draw_vehicle_fallback_car(c, sx, sy, rect, line, txt, lambda pts, fill, outline="#434c56", stroke=1:
                                            c.create_polygon(*[v*(sx if i%2==0 else sy) for p in pts for i,v in enumerate(p)],
                                                             fill=fill, outline=outline, width=stroke))
        temps=read("tyre_temp_c")
        pressures=read("tyre_press_kpa")
        def arr(data,i,unit,precision=0,conv=None):
            try:
                v=data[i]
                if conv is not None and v is not None: v=conv(v)
                return fmt(v,unit,precision)
            except (IndexError,TypeError): return "—"
        wstate = wheel_levels(wheelsd)
        # Data in model is ordered FL, FR, RL, RR.
        for i,(x,y,side,key) in enumerate(((25,136,"L","fl"),(560,136,"R","fr"),(25,415,"L","rl"),(560,415,"R","rr"))):
            ty=y+77
            edge=250 if side=="L" else 510                 # gorsel yoksa govde kenari
            if drawn is not None:
                x0,y0,x1,y1=drawn["wheels"][key]
                ty=((y0+y1)/2)/sy
                y=max(62,min(440,ty-77))
                edge=(x0 if side=="L" else x1)/sx
            card(x,y,175,150)
            st=wstate[i]
            if st is None:
                txt(x+14,y+24,"SÜSP.  —",12,"#ff9d2e",bold=True)
            else:
                txt(x+14,y+24,"SÜSP.  "+("SAĞLAM" if st==0 else "KIRIK" if st==STEPS-1 else "HASARLI"),12,color_of(st),bold=True)
            line(x+12,y+42,x+163,y+42,"#343b45")
            try: tval=temps[i]
            except (IndexError,TypeError): tval=None
            tcol=tyre_temp.temp_color(tval,trange)
            rect(x,y,x+175,y+4,fill=tcol)                  # kartın üst kenarında sıcaklık rengi şeridi
            txt(x+14,y+76,arr(temps,i,"°C"),22,tcol,bold=True)
            tstat=tyre_temp.temp_status(tval,trange)
            if tstat: txt(x+100,y+76,tstat,10,tcol,bold=True)
            if drawn is not None and tstat:                # tekerlek üzerinde sıcaklık şeridi
                wx0,wy0,wx1,wy1=drawn["wheels"][key]
                ww,wh=wx1-wx0,wy1-wy0
                c.create_rectangle(wx0+ww*.34,wy0+wh*.14,wx0+ww*.66,wy0+wh*.86,fill=tcol,outline="")
            txt(x+14,y+109,arr(pressures,i," psi",1,kpa_to_psi),15,"#aeb8c5")
            warn=wheel_warning(key,st)
            if warn: txt(x+14,y+134,"⚠ "+warn,11,RED,bold=True)
            else: txt(x+14,y+134,"Aşınma: —",11,"#91a0af")
            cx=x+175 if side=="L" else x
            line(cx,y+77 if drawn is not None else ty,edge,ty,"#8d99a6")
        card(20,592,720,42)
        txt(38,614,"YAKIT",12,"#ff9d2e",bold=True)
        txt(100,614,fmt(read("fuel_l")," L",1),14,bold=True)
        txt(205,614,"HASAR (ham)",12,"#ff9d2e",bold=True)
        raw=summary_text(body)
        if frame is None:
            txt(335,614,"Veri yok",10,"#aeb8c5")
        elif raw is None:
            txt(335,614,"Oyun bölgesel hasar verisi vermiyor",10,"#aeb8c5")
        else:
            txt(335,614,raw,10,"#aeb8c5")

    def _drag_start(self, event):
        self._drag_origin = (event.x_root, event.y_root, self.win.winfo_x(), self.win.winfo_y())

    def _drag(self, event):
        if not hasattr(self, "_drag_origin"):
            return
        sx, sy, x, y = self._drag_origin
        self.win.geometry("+%d+%d" % (x + event.x_root - sx, y + event.y_root - sy))

    def _resize_start(self, event):
        self._resize_origin = (event.x_root, event.y_root,
                               self.win.winfo_width(), self.win.winfo_height())

    def _resize_drag(self, event):
        if not hasattr(self, "_resize_origin"):
            return
        sx, sy, width, height = self._resize_origin
        new_w = max(200, width + event.x_root - sx)
        new_h = max(90, height + event.y_root - sy)
        self.win.geometry(f"{new_w}x{new_h}")

    def update(self, frame, running):
        if self.key == "pedals":
            live = frame is not None and getattr(frame, "live", False) and running
            gas = getattr(frame, "throttle", None) if live else None
            brake = getattr(frame, "brake", None) if live else None
            def normalize(v):
                try:
                    return max(0., min(1., float(v))) if v is not None else None
                except (TypeError, ValueError):
                    return None
            gas, brake = normalize(gas), normalize(brake)
            now = time.monotonic()
            if live and (gas is not None or brake is not None):
                self.history.append((now, gas, brake))
            duration = self.manager.history_seconds.get(self.key, 5)
            while self.history and self.history[0][0] < now-duration:
                self.history.popleft()
            self._draw_pedals(gas, brake)
            return
        if self.key in ("tyres", "parts"):
            self._vehicle_frame = frame if frame is not None and getattr(frame, "live", False) and running else None
            self._redraw()
            return
        if frame is None or not getattr(frame, "live", False) or not running:
            text = "PITAPEX\nTelemetri bekleniyor"
        elif self.key == "speed":
            v = getattr(frame, "speed_kmh", None)
            text = "HIZ\n%s" % ("—" if v is None else "%.0f km/h" % v)
        elif self.key == "pedals":
            gas, brake = getattr(frame, "throttle", None), getattr(frame, "brake", None)
            text = "PEDALLAR\nGaz  %s    Fren  %s" % ("—" if gas is None else "%d%%" % round(gas*100),
                                                        "—" if brake is None else "%d%%" % round(brake*100))
        elif self.key == "rpm":
            rpm, gear = getattr(frame, "rpm", None), getattr(frame, "gear", None)
            text = "DEVİR / VİTES\n%s RPM     %s" % ("—" if rpm is None else "%.0f" % rpm,
                                                      gear_text(gear) or "—")
        else:
            lap, best = getattr(frame, "lap_count", None), getattr(frame, "lap_best_ms", None)
            current = getattr(frame, "lap_current_ms", None)
            text = "TUR BİLGİSİ\nTur %s   Anlık %s\nEn iyi %s" % (
                "—" if lap is None else lap, fmt_ms(current) or "—", fmt_ms(best) or "—")
        text = translate(text, getattr(self.manager.app, "language", "tr"))
        self.label.config(text=text, bg=self._label_bg(), fg="#f1f2f4", font=("Segoe UI", 16, "bold"))

    def geometry(self):
        return self.win.geometry()

    def destroy(self):
        try:
            if self.background is not None:
                self.background.destroy()
            self.win.destroy()
        except tk.TclError:
            pass


class OverlayManager:
    def __init__(self, app):
        self.app = app
        self.windows = {}
        self.saved = app.prefs.get("overlay_geometry", {}) or {}
        self.opacity = app.prefs.get("overlay_opacity", {}) or {}
        self.history_seconds = app.prefs.get("overlay_history_seconds", {}) or {}
        self.tyre_cfg = tyre_temp.normalize_config(app.prefs.get("tyre_temp", {}))
        self._save_job = None
        self._car_assets = None
        self._car_assets_tried = False

    # ---- saydamlik ----
    # Kayit anahtari "overlay_opacity" ESKI ANLAMIYLA kalir (arka planin gorunurlugu, %10-100); boylece
    # onceki surumlerin kayitlari aynen gecerlidir. Arayuzde gosterilen SAYDAMLIK = 100 - opacity.
    def opacity_of(self, key):
        try:
            return max(10, min(100, int(round(float(self.opacity.get(key, 100))))))
        except (TypeError, ValueError):
            return 100

    def transparency(self, key):
        return 100 - self.opacity_of(key)

    def set_transparency(self, key, value):
        t = max(0, min(MAX_TRANSPARENCY, int(round(float(value)))))
        self.set_opacity(key, 100 - t)

    def car_assets(self):
        """Arac gorselleri (varsa). Yoksa/acilamazsa None: HUD eski poligon araca doner."""
        if not self._car_assets_tried:
            self._car_assets_tried = True
            try:
                assets = CarAssets(lambda path: tk.PhotoImage(master=self.app.root, file=path))
                self._car_assets = assets if assets.available else None
            except Exception:
                self._car_assets = None
        return self._car_assets

    def _schedule_save(self):
        if self._save_job is None:
            self._save_job = self.app.root.after(600, self._flush_job)

    def _flush_job(self):
        self._save_job = None
        self.app.prefs.set("overlay_opacity", dict(self.opacity))

    def flush(self):
        """Bekleyen saydamlik kaydini hemen yaz (kaydirici surulurken diske her adimda yazilmaz)."""
        if self._save_job is not None:
            try:
                self.app.root.after_cancel(self._save_job)
            except Exception:
                pass
            self._save_job = None
            self.app.prefs.set("overlay_opacity", dict(self.opacity))

    def default_geometry(self, key):
        positions = {"speed": "260x90+30+100", "pedals": "470x155+30+205",
                     "rpm": "300x90+30+310", "lap": "320x115+30+415", "tyres": "760x650+350+100", "parts": "520x650+890+100"}
        return self.saved.get(key) or positions[key]

    def open(self, key):
        if key not in OVERLAYS:
            return
        if key not in self.windows:
            self.windows[key] = OverlayWindow(self, key)
        self.windows[key].win.deiconify()

    def save_window(self, key):
        obj = self.windows.get(key)
        if obj:
            self._save_geometry(key, obj.geometry())

    def set_opacity(self, key, value):
        self.opacity[key] = max(10, min(100, int(round(float(value)))))
        if key in self.windows:
            self.windows[key].apply_opacity()
        self._schedule_save()

    def set_tyre_cfg(self, cfg):
        """Lastik sıcaklığı ayarını (mod + kuru/ıslak aralıklar) doğrulayıp kaydeder; ValueError fırlatabilir."""
        clean = tyre_temp.normalize_config(cfg)
        for name in ("dry", "wet"):                        # normalize_config bozuk aralığı sessizce varsayılana çevirir; burada reddet
            tyre_temp.validate((cfg.get("ranges") or {}).get(name))
        self.tyre_cfg = clean
        self.app.prefs.set("tyre_temp", clean)
        win = self.windows.get("tyres")
        if win is not None:
            win._redraw()

    def set_size(self, key, width, height):
        obj = self.windows.get(key)
        if obj:
            obj.win.geometry(f"{int(width)}x{int(height)}")
            self.save_window(key)
        else:
            import re
            old = self.default_geometry(key)
            match = re.match(r"\d+x\d+([+-]\d+[+-]\d+)", old)
            self._save_geometry(key, f"{int(width)}x{int(height)}{match.group(1) if match else '+30+100'}")

    def set_history_seconds(self, seconds):
        self.history_seconds["pedals"] = int(seconds)
        self.app.prefs.set("overlay_history_seconds", self.history_seconds)

    def close(self, key):
        obj = self.windows.pop(key, None)
        if obj:
            self._save_geometry(key, obj.geometry())
            obj.destroy()

    def _save_geometry(self, key, geometry):
        self.saved[key] = geometry
        self.app.prefs.set("overlay_geometry", self.saved)

    def close_all(self):
        for key in list(self.windows):
            self.close(key)
        self.flush()

    def update(self):
        state = self.app.telemetry.state()
        for window in list(self.windows.values()):
            try:
                window.update(state.get("frame"), state.get("running", False))
            except tk.TclError:
                pass


class OverlaysPage(ttk.Frame):
    """Sekmeli overlay yönetimi; çalışan overlay motorunu değiştirmez."""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.manager = app.overlays
        self.vars = {}
        self.opacity_vars = {}
        self.width_vars = {}
        self.height_vars = {}
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Overlay pencerelerini ayrı ayrı yönet. Pencereyi sürükleyerek taşı; sağ alt köşeden boyutlandır.",
                  style="Muted.TLabel", wraplength=800).grid(row=0,column=0,sticky="w",padx=12,pady=10)
        style = ttk.Style(self)
        style.configure("PitApexOverlay.TNotebook", background="#121212", borderwidth=0)
        style.configure("PitApexOverlay.TNotebook.Tab", background="#161616", foreground="#a65a23",
                        padding=(15, 9), font=("Segoe UI", 10, "bold"))
        style.map("PitApexOverlay.TNotebook.Tab",
                  background=[("selected", "#a65a23"), ("active", "#292929")],
                  foreground=[("selected", "#000000"), ("active", "#bd7944")])
        self.tabs = ttk.Notebook(self, style="PitApexOverlay.TNotebook")
        self.tabs.grid(row=1,column=0,sticky="nsew",padx=10,pady=5)
        self.rowconfigure(1,weight=1)
        # Eski overlay sürümündeki gibi ayrı sekmeler; aktif çalışan
        # overlay pencereleri önceki paketin kodundan gelir.
        order = ("pedals", "tyres", "parts", "speed", "rpm", "lap")
        for key in order:
            name, desc = OVERLAYS[key]
            panel = ttk.Frame(self.tabs, padding=16)
            self.tabs.add(panel, text=name)
            panel.columnconfigure(1,weight=1)
            var=tk.BooleanVar(value=key in self.manager.windows)
            self.vars[key]=var
            ttk.Checkbutton(panel,text="Overlay penceresini göster",variable=var,
                            command=lambda k=key:self.toggle(k)).grid(row=0,column=0,columnspan=2,sticky="w",pady=8)
            ttk.Label(panel,text=desc,style="Muted.TLabel").grid(row=1,column=0,columnspan=2,sticky="w",pady=4)
            transparency=tk.IntVar(value=self.manager.transparency(key))
            self.opacity_vars[key]=transparency      # (ad eski; deger artik SAYDAMLIK yuzdesi)
            ttk.Label(panel,text="Arka plan saydamlığı (%)").grid(row=2,column=0,sticky="w",pady=8)
            tk.Scale(panel,from_=0,to=MAX_TRANSPARENCY,orient="horizontal",variable=transparency,length=220,
                     command=lambda v,k=key:self.manager.set_transparency(k,float(v))).grid(row=2,column=1,sticky="w")
            ttk.Label(panel,text="Artınca arka plan kaybolur; yazılar ve göstergeler net kalır. %0 = tam opak.",
                      style="Muted.TLabel",wraplength=260).grid(row=2,column=2,sticky="w",padx=10)
            dims=re.match(r"(\d+)x(\d+)",self.manager.default_geometry(key))
            width=tk.IntVar(value=int(dims.group(1)) if dims else 300)
            height=tk.IntVar(value=int(dims.group(2)) if dims else 120)
            self.width_vars[key],self.height_vars[key]=width,height
            ttk.Label(panel,text="Genişlik").grid(row=3,column=0,sticky="w",pady=5)
            ttk.Spinbox(panel,from_=200,to=1600,textvariable=width,width=9).grid(row=3,column=1,sticky="w")
            ttk.Label(panel,text="Yükseklik").grid(row=4,column=0,sticky="w",pady=5)
            ttk.Spinbox(panel,from_=90,to=1000,textvariable=height,width=9).grid(row=4,column=1,sticky="w")
            ttk.Button(panel,text="Boyutu uygula",command=lambda k=key:self.resize(k)).grid(row=5,column=1,sticky="w",pady=10)
            if key=="tyres":
                self._build_tyre_temp_panel(panel)
            if key=="pedals":
                ttk.Label(panel,text="Grafik geçmişi (saniye)").grid(row=6,column=0,sticky="w",pady=6)
                self.history_var=tk.IntVar(value=int(self.manager.history_seconds.get("pedals",5)))
                ttk.Combobox(panel,values=(5,10),textvariable=self.history_var,width=7,state="readonly").grid(row=6,column=1,sticky="w")
                ttk.Button(panel,text="Grafik süresini uygula",command=lambda:self.manager.set_history_seconds(self.history_var.get())).grid(row=7,column=1,sticky="w",pady=6)
        actions=ttk.Frame(self)
        actions.grid(row=2,column=0,sticky="w",padx=12,pady=8)
        ttk.Button(actions,text="Tümünü aç",command=self.open_all).pack(side="left",padx=4)
        ttk.Button(actions,text="Tümünü kapat",command=self.close_all).pack(side="left",padx=4)

    def _build_tyre_temp_panel(self,panel):
        cfg=self.manager.tyre_cfg
        box=ttk.LabelFrame(panel,text="Lastik sıcaklığı renkleri",padding=10)
        box.grid(row=8,column=0,columnspan=3,sticky="we",pady=12)
        ttk.Label(box,text="Hangi aralığın kullanılacağı oyunun gerçek lastik tipinden (kuru/ıslak) otomatik seçilir. "
                           "Oyun tip vermiyorsa (ör. iRacing) aşağıdaki yedek profil kullanılır; varsayılan değerler doğrulanmış ideal değerler DEĞİLDİR, kendine göre ayarla.",
                  style="Muted.TLabel",wraplength=640).grid(row=0,column=0,columnspan=6,sticky="w",pady=(0,8))
        self.tyre_mode_var=tk.StringVar(value=tyre_temp.MODE_LABELS[cfg["mode"]])
        self.tyre_fallback_var=tk.StringVar(value="Kuru" if cfg["fallback"]=="dry" else "Islak")
        ttk.Label(box,text="Mod").grid(row=1,column=0,sticky="w",pady=4)
        ttk.Combobox(box,values=[tyre_temp.MODE_LABELS[m] for m in tyre_temp.MODES],textvariable=self.tyre_mode_var,
                     width=12,state="readonly").grid(row=1,column=1,sticky="w")
        ttk.Label(box,text="Oyun tip vermezse").grid(row=1,column=2,sticky="e",padx=(16,4))
        ttk.Combobox(box,values=("Kuru","Islak"),textvariable=self.tyre_fallback_var,width=8,
                     state="readonly").grid(row=1,column=3,sticky="w")
        self.tyre_vars={}
        for r,(name,title) in enumerate((("dry","KURU (°C)"),("wet","ISLAK (°C)")),start=2):
            ttk.Label(box,text=title,font=("Segoe UI",9,"bold")).grid(row=r*2,column=0,sticky="w",pady=(10,0))
            for c,k in enumerate(tyre_temp.KEYS):
                ttk.Label(box,text=tyre_temp.KEY_LABELS[k]).grid(row=r*2,column=1+c,sticky="w",padx=6,pady=(10,0))
                var=tk.StringVar(value=("%g"%cfg["ranges"][name][k]))
                self.tyre_vars[(name,k)]=var
                ttk.Spinbox(box,from_=tyre_temp.LIMITS[0],to=tyre_temp.LIMITS[1],textvariable=var,width=8).grid(
                    row=r*2+1,column=1+c,sticky="w",padx=6)
        self.tyre_msg=ttk.Label(box,text="",style="Muted.TLabel")
        self.tyre_msg.grid(row=9,column=0,columnspan=6,sticky="w",pady=(8,0))
        bar=ttk.Frame(box); bar.grid(row=10,column=0,columnspan=6,sticky="w",pady=6)
        ttk.Button(bar,text="Uygula",command=self.apply_tyre_temp).pack(side="left",padx=(0,6))
        ttk.Button(bar,text="Varsayılana dön",command=self.reset_tyre_temp).pack(side="left")

    def _tyre_cfg_from_ui(self):
        inv={v:k for k,v in tyre_temp.MODE_LABELS.items()}
        return {"mode":inv.get(self.tyre_mode_var.get(),"auto"),
                "fallback":"wet" if self.tyre_fallback_var.get()=="Islak" else "dry",
                "ranges":{n:{k:self.tyre_vars[(n,k)].get().replace(",",".") for k in tyre_temp.KEYS} for n in ("dry","wet")}}

    def apply_tyre_temp(self):
        cfg=self._tyre_cfg_from_ui()
        try:
            for n in ("dry","wet"):
                try: tyre_temp.validate(cfg["ranges"][n])
                except ValueError as e: raise ValueError("%s: %s"%("Kuru" if n=="dry" else "Islak",e))
            self.manager.set_tyre_cfg(cfg)
        except ValueError as e:
            self.tyre_msg.config(text="Kaydedilmedi — %s"%e)
            return False
        self.tyre_msg.config(text="Kaydedildi.")
        return True

    def reset_tyre_temp(self):
        for n in ("dry","wet"):
            for k in tyre_temp.KEYS:
                self.tyre_vars[(n,k)].set("%g"%tyre_temp.DEFAULT_RANGES[n][k])
        self.tyre_mode_var.set(tyre_temp.MODE_LABELS["auto"]); self.tyre_fallback_var.set("Kuru")
        self.apply_tyre_temp()

    def resize(self,key):
        self.manager.set_size(key,max(200,self.width_vars[key].get()),max(90,self.height_vars[key].get()))

    def toggle(self,key):
        if self.vars[key].get():self.manager.open(key)
        else:self.manager.close(key)

    def open_all(self):
        for key in OVERLAYS:
            self.vars[key].set(True)
            self.manager.open(key)

    def close_all(self):
        self.manager.close_all()
        for var in self.vars.values():var.set(False)
