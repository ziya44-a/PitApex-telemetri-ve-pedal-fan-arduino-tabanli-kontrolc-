"""PitApex ana penceresi: ust bilgi, ortak Arduino baglantisi, 4 sayfa."""
import copy
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox

from core.engine import DEFAULTS, Engine
from core.session import SessionTracker
from core.telemetry_manager import GAME_NAMES, TelemetryManager
from hardware.arduino import ArduinoLink, LedLink, list_port_names
from hardware.fan import FanController
from hardware.led import LedController
from storage.paths import resource_path
from storage.records import RecordStore
from storage.sessions import SessionStore
from storage.settings import PedalSettings, Preferences, Profiles
from ui.dialogs import SettingsWindow
from ui.fan_page import FanPage
from ui.game_info_page import GameInfoPage
from ui.led_page import LedPage
from ui.scroll_host import ScrollHost
from ui.pedals_page import PedalsPage
from ui.records_page import RecordsPage
from ui.statistics_page import StatisticsPage
from ui.overlays_page import OverlaysPage, OverlayManager
from ui.themes import Theme
from ui.i18n import apply_language, translate

TABS = ["Pedallar", "Fan", "LED Aydınlatma", "Oyun Bilgileri", "Kaydedilen Rekorlar", "İstatistikler", "Overlay Yönetimi"]


class App:
    def __init__(self, root, dm):
        self.root, self.dm = root, dm
        root.title("PitApex")
        self.prefs = Preferences(dm)
        self.language = self.prefs.get("language", "tr")
        self.theme = Theme(self.prefs.get("theme", "dark"))
        self.theme.apply(root)
        try:                                   # pencere / görev çubuğu simgesi
            root.iconbitmap(resource_path("assets", "pitapex.ico"))
        except Exception:
            pass
        self.pedal_store = PedalSettings(dm)
        self.profiles = Profiles(dm)
        self.records = RecordStore(dm)
        self.sessions = SessionStore(dm)

        # --- donanım ve motorlar (hepsi birbirinden bağımsız iş parçacıkları) ---
        self.link = ArduinoLink()
        self.cfg = copy.deepcopy(DEFAULTS)
        self.engine = Engine(self.cfg, self.link)
        self.fan = FanController(self.link, self.engine, lambda: self.fan_page.get_cfg())
        self.led_link = LedLink()           # LED kartı AYRI Arduino: pedal/fan bağlantısından bağımsız
        self.led = LedController(self.led_link, self.engine, lambda: self.led_page.get_cfg())
        self.tracker = SessionTracker(self.records, self.sessions, GAME_NAMES)
        self.telemetry = TelemetryManager(self.tracker)

        self._seen_record_event = None
        self._toast = None
        self._toast_after = None
        self.overlays = OverlayManager(self)
        self.build_ui()
        self.engine.start()
        self.fan.start()
        self.led.start()
        self.telemetry.start()
        self.refresh_ports()
        self.n = 0
        self._last_connection_display = None
        self._last_status_display = None
        self.tick()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- arayüz ----------------
    def build_ui(self):
        r = self.root
        r.columnconfigure(0, weight=1)
        r.rowconfigure(3, weight=1)

        head = ttk.Frame(r)
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        try:
            self.logo = tk.PhotoImage(file=resource_path("assets", "logo_56.png"))
            ttk.Label(head, image=self.logo).pack(side="left")
        except Exception:
            self.logo = None
        ttk.Label(head, text="PitApex", style="Title.TLabel").pack(side="left", padx=10)
        ttk.Label(head, text="Sim racing donanım ve telemetri merkezi", style="Muted.TLabel").pack(side="left", padx=4)
        ttk.Button(head, text="⚙ Ayarlar", command=self.open_settings).pack(side="right")

        # Two clearly separated navigation groups; retain stable tab indices
        # so existing last_tab preferences and page routing remain compatible.
        tabs = ttk.Frame(r)
        tabs.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 3))
        self.tab_var = tk.IntVar(value=0)
        self.nav_groups = []
        groups = (("DONANIM", "HARDWARE", (0, 1, 2)),
                  ("TELEMETRI VE KAYITLAR", "TELEMETRY & RECORDS", (3, 4, 5, 6)))
        for group_row, (tr_title, en_title, indices) in enumerate(groups):
            line = ttk.Frame(tabs)
            line.grid(row=group_row, column=0, sticky="w", pady=(0, 4))
            title = ttk.Label(line, text=tr_title, style="Muted.TLabel")
            title.pack(side="left", padx=(2, 12))
            self.nav_groups.append((title, tr_title, en_title))
            for i in indices:
                ttk.Radiobutton(line, text=TABS[i], value=i, variable=self.tab_var,
                                style="Tab.Toolbutton", command=self.show_tab).pack(side="left", padx=(0, 5))

        # ortak Arduino bağlantısı (pedal ve fan aynı portu kullanır)
        top = ttk.LabelFrame(r, text="Arduino bağlantısı (pedal + fan ortak)")
        top.grid(row=2, column=0, sticky="ew", padx=10, pady=6)
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=28, state="readonly")
        self.port_box.grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(top, text="Yenile", command=self.refresh_ports).grid(row=0, column=1, padx=2)
        self.conn_btn = ttk.Button(top, text="Bağlan", command=self.toggle_conn)
        self.conn_btn.grid(row=0, column=2, padx=2)
        self.conn_lbl = ttk.Label(top, text="Bağlı değil", style="Muted.TLabel")
        self.conn_lbl.grid(row=0, column=3, padx=8)
        self.lat_lbl = ttk.Label(top, text="Gecikme: -")
        self.lat_lbl.grid(row=0, column=4, padx=8)
        self.telemetry_status = ttk.Label(top, text="● Veri bekleniyor", style="Muted.TLabel")
        self.telemetry_status.grid(row=0, column=5, padx=8)
        self.banner = ttk.Label(top, text="", style="Warn.TLabel")
        self.banner.grid(row=1, column=0, columnspan=5, sticky="w", padx=6)

        self.container = ttk.Frame(r)
        self.container.grid(row=3, column=0, sticky="nsew", padx=4, pady=2)
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)
        self.pedals_page = PedalsPage(self.container, self)
        self.scroll_hosts = [ScrollHost(self.container, self.theme.c["bg"]) for _ in range(6)]
        self.fan_page = FanPage(self.scroll_hosts[0].body, self)
        # Fixed LED preview lives outside the scrollable canvas.
        led_host = self.scroll_hosts[1]
        led_host.columnconfigure(0, weight=1)
        led_host.columnconfigure(2, weight=0)
        self.led_preview_dock = ttk.Frame(led_host)
        self.led_preview_dock.grid(row=0, column=2, sticky="n", padx=(6, 8), pady=6)
        self.led_page = LedPage(led_host.body, self, preview_parent=self.led_preview_dock)
        self.info_page = GameInfoPage(self.scroll_hosts[2].body, self)
        self.records_page = RecordsPage(self.scroll_hosts[3].body, self)
        self.statistics_page = StatisticsPage(self.scroll_hosts[4].body, self)
        self.overlays_page = OverlaysPage(self.scroll_hosts[5].body, self)
        self.pages = [self.pedals_page, self.fan_page, self.led_page, self.info_page, self.records_page, self.statistics_page, self.overlays_page]
        self.pedals_page.grid(row=0, column=0, sticky="nsew")
        for host, page in zip(self.scroll_hosts, self.pages[1:]):
            host.grid(row=0, column=0, sticky="nsew")
            page.grid(row=0, column=0, sticky="nsew")
        last = self.prefs.get("last_tab", 0)
        self.tab_var.set(last if isinstance(last, int) and 0 <= last < len(TABS) else 0)
        self.show_tab()
        self.set_language(self.language)

    def show_tab(self):
        i = self.tab_var.get()
        (self.pedals_page if i == 0 else self.scroll_hosts[i-1]).tkraise()
        self.current = i
        self.prefs.set("last_tab", i)

    # ---------------- bağlantı ----------------
    def refresh_ports(self):
        names = list_port_names()
        self.port_box["values"] = names
        for n in names:
            if "arduino" in n.lower() or "ch340" in n.lower():
                self.port_var.set(n)
                return
        if names and not self.port_var.get():
            self.port_var.set(names[0])

    def toggle_conn(self):
        if self.link.connected:
            self.engine.disconnect()
            self.conn_btn.config(text=translate("Bağlan", self.language))
            return
        sel = self.port_var.get()
        if not sel:
            messagebox.showinfo("PitApex", "Önce bir port seç.")
            return
        try:
            self.engine.connect(sel.split(" ")[0])
            self.conn_btn.config(text=translate("Kes", self.language))
        except Exception as e:
            messagebox.showerror("PitApex", "Bağlanılamadı:\n%s\n\nSimHub ya da Arduino IDE "
                                 "Serial Monitor açıksa kapat." % e)

    def update_connection(self):
        L = self.link
        c = self.theme.c
        self.banner.config(text=translate(L.error, self.language))
        if L.error and not L.connected:
            self.conn_btn.config(text=translate("Bağlan", self.language))
        if L.connected:
            self.conn_btn.config(text=translate("Kes", self.language))
            if time.time() < L.ready_at:
                self.conn_lbl.config(text="Arduino hazırlanıyor...", foreground=c["warn"])
            elif L.fw_ok:
                txt = "Bağlı (kod v%s)" % L.fw_version
                if not L.fan_supported:
                    txt += " · fan için v3 kodu gerekli"
                elif not L.multi_output:
                    txt += " · M3/M4 ve 2. fan için v4 kodu gerekli"
                self.conn_lbl.config(text=translate(txt, self.language), foreground=c["ok"])
            elif time.time() > L.ready_at + 3.0:
                self.conn_lbl.config(text=translate("Arduino kodu eski/uyumsuz! PedalHaptic.ino'yu yeniden yükle", self.language),
                                     foreground=c["warn"])
            else:
                self.conn_lbl.config(text=translate("Bağlı", self.language), foreground=c["ok"])
        else:
            self.conn_lbl.config(text=translate("Bağlı değil", self.language), foreground=c["muted"])
            self.conn_btn.config(text=translate("Bağlan", self.language))
        if L.latency is not None:
            self.lat_lbl.config(text=("Serial latency: %.1f ms (max %.1f) | loop: %d Hz" if self.language == "en" else "Seri gecikme: %.1f ms (maks %.1f) | döngü: %d Hz")
                                % (L.latency, L.lat_max, self.engine.hz))
        else:
            self.lat_lbl.config(text=("Latency: - | loop: %d Hz" if self.language == "en" else "Gecikme: - | döngü: %d Hz") % self.engine.hz)

    def notify_record(self, event):
        """Non-modal toast on the Tk main thread; deduplicated by event identity."""
        if not event or not event.startswith("Yeni rekor:") or event == self._seen_record_event:
            return
        self._seen_record_event = event
        if self._toast_after is not None:
            try: self.root.after_cancel(self._toast_after)
            except tk.TclError: pass
        if self._toast is not None:
            self._toast.destroy()
        self._toast = ttk.Label(self.root, text="🏆 " + translate(event, self.language), style="Title.TLabel")
        self._toast.place(relx=0.5, rely=0.02, anchor="n")
        def dismiss():
            if self._toast is not None:
                self._toast.destroy()
                self._toast = None
            self._toast_after = None
        self._toast_after = self.root.after(3500, dismiss)

    def apply_imported_settings(self):
        """Synchronize imported preferences with live controllers without touching history."""
        self.set_theme(self.prefs.get("theme", "dark"))
        self.set_language(self.prefs.get("language", "tr"))
        self.pedals_page.load_settings()
        self.pedals_page.sync_cfg()
        self.fan_page.load_prefs(self.prefs.get("fan", {}))
        self.led_page.load_prefs(self.prefs.get("led", {}))
        self.pedals_page._last_saved = self.pedals_page._snapshot()
        apply_language(self.root, self.language)
        for widget, tr_title, en_title in self.nav_groups:
            widget.configure(text=en_title if self.language == "en" else tr_title)

    # ---------------- tema / ayarlar ----------------
    def set_theme(self, name):
        self.theme.set(name, self.root)
        self.prefs.set("theme", name)

    def set_language(self, language):
        self.language = language if language in ("tr", "en") else "tr"
        self.prefs.set("language", self.language)
        apply_language(self.root, self.language)
        for widget, tr_title, en_title in self.nav_groups:
            widget.configure(text=en_title if self.language == "en" else tr_title)

    def open_settings(self):
        SettingsWindow(self.root, self)

    # ---------------- tüm veriyi temizle ----------------
    def wipe_all(self):
        """(başarılı_mı, mesaj). Program dosyalarına dokunmaz; sonra temiz veriyle çalışmaya devam eder."""
        try:
            with self.tracker.lock, self.records.lock, self.sessions.lock:
                self.tracker.reset_all()
                removed, errors = self.dm.wipe_user_data()
                self.records.reset()
                self.sessions.reset()
                self.prefs.reset()
        except Exception as e:
            return False, "Temizleme sırasında hata oluştu:\n%s" % e
        self.pedals_page.reset_after_wipe()
        self.fan_page.reset_after_wipe()
        self.led_page.reset_after_wipe()
        self.theme.set("dark", self.root)
        self.records_page.refresh(force=True)
        if errors:
            return False, "Bazı dosyalar silinemedi:\n" + "\n".join(errors[:5])
        return True, "Tüm kullanıcı verileri temizlendi. PitApex temiz veriyle çalışmaya devam ediyor."

    # ---------------- döngü ----------------
    def tick(self):
        try:
            self.n += 1
            cur = self.current
            self.pedals_page.tick(cur == 0)
            if self.n % 5 == 1:
                self.update_connection()
            snap = self.tracker.snapshot()
            event = snap.get("last_event", "")
            if event != getattr(self, "_last_tracker_event", None):
                self._last_tracker_event = event
                if event.startswith("Yeni rekor:"):
                    self.notify_record(event)
            telemetry_state = self.telemetry.state()
            frame = telemetry_state.get("frame")
            live = bool(frame is not None and getattr(frame, "live", False))
            if self.n % 5 == 1:
                self.telemetry_status.configure(text=translate("● Bağlandı" if live else ("● Bağlantı kesildi" if telemetry_state.get("running") and frame is None else "● Veri bekleniyor"), self.language),
                                                foreground=self.theme.c["ok"] if live else self.theme.c["muted"])
            if self.n % 2 == 0:
                self.overlays.update()
            # Full widget-tree translation every 480 ms caused resize stutter.
            # Translate static UI only when language changes; dynamic labels translate at source.
            if self.n % 6 == 0:                  # ~240 ms: ağır olmayan sayfalar
                pg = self.pages
                self.fan_page.tick(cur == pg.index(self.fan_page))
                self.led_page.tick(cur == pg.index(self.led_page))
                self.info_page.tick(cur == pg.index(self.info_page))
                self.records_page.tick(cur == pg.index(self.records_page))
                self.statistics_page.tick(cur == pg.index(self.statistics_page))
        except Exception as e:                   # arayüz hatası hiçbir motoru durdurmasın
            self.banner.config(text=translate("Arayüz hatası:", self.language) + " " + str(e))
        self.root.after(40, self.tick)

    def on_close(self):
        try:
            self.pedals_page.save_settings()
            self.fan_page.sync()
            self.fan_page.autosave()
            self.led_page.sync()
            self.led_page.autosave()
        except Exception:
            pass
        self.overlays.close_all()
        self.fan.running = False
        self.led.running = False
        try:
            self.led_link.disconnect()          # LED kartı ekranı temizler
        except Exception:
            pass
        self.telemetry.stop()
        self.engine.running = False
        time.sleep(0.1)
        self.engine.disconnect()
        try:
            self.engine.src.close()
        except Exception:
            pass
        self.root.destroy()
