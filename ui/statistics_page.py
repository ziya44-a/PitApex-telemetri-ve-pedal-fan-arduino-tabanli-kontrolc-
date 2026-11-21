"""PitApex session history: persistent statistics and lap inspection."""
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from core.models import fmt_ms


def duration(s):
    try:
        a = datetime.strptime(s["started"][:19], "%Y-%m-%d %H:%M:%S")
        b = datetime.strptime((s.get("ended_at") or s.get("updated") or s["started"])[:19], "%Y-%m-%d %H:%M:%S")
        n = max(0, int((b-a).total_seconds()))
        return f"{n//3600:02d}:{n//60%60:02d}:{n%60:02d}"
    except (ValueError, KeyError, TypeError):
        return "—"


class StatisticsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app, self.version, self.selected = app, None, None
        self.sessions_by_id = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=3)
        self.rowconfigure(4, weight=2)
        head = ttk.Frame(self)
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Label(head, text="Oturum İstatistikleri", style="Big.TLabel").pack(side="left")
        ttk.Button(head, text="Yenile", command=lambda: self.refresh(True)).pack(side="right")
        filters = ttk.Frame(self)
        filters.grid(row=1, column=0, sticky="ew", padx=10, pady=3)
        ttk.Label(filters, text="Oyun:").pack(side="left")
        self.game = tk.StringVar(value="Tümü")
        self.game_box = ttk.Combobox(filters, textvariable=self.game, state="readonly", width=24, values=["Tümü"])
        self.game_box.pack(side="left", padx=8)
        self.game_box.bind("<<ComboboxSelected>>", lambda e: self.refresh(True))
        self.extra_filters = {}
        for key, label, width in (("track", "Pist", 19), ("car", "Araç", 19), ("type", "Tür", 14), ("date", "Tarih", 13)):
            ttk.Label(filters, text=label + ":").pack(side="left", padx=(5, 1))
            v = tk.StringVar(value="Tümü")
            cb = ttk.Combobox(filters, textvariable=v, state="readonly", width=width, values=["Tümü"])
            cb.pack(side="left", padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self.refresh(True))
            self.extra_filters[key] = (v, cb)
        columns = ("date", "game", "track", "car", "type", "duration", "laps", "best")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse", height=10)
        for key, label, width in [("date","Tarih",145),("game","Oyun",110),("track","Pist",170),
                                  ("car","Araç",160),("type","Oturum",105),("duration","Süre",85),
                                  ("laps","Turlar",80),("best","En hızlı tur",110)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=65, anchor="w" if key in ("track","car") else "center")
        self.tree.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self.show_laps)
        ttk.Label(self, text="Seçilen oturumun turları  •  Yeşil: geçerli  •  Kırmızı: geçersiz  •  Gri: eski kayıtta durum bilinmiyor", style="Muted.TLabel").grid(row=3, column=0, sticky="w", padx=12, pady=5)
        lap_cols = ("number", "time", "delta", "status", "reason")
        self.laps = ttk.Treeview(self, columns=lap_cols, show="headings", height=7)
        for key, label, width in [("number","Tur",70),("time","Tur süresi",120),("delta","Fark",90),("status","Durum",125),("reason","Açıklama",490)]:
            self.laps.heading(key, text=label)
            self.laps.column(key, width=width, anchor="center" if key != "reason" else "w")
        self.laps.tag_configure("valid", foreground="#38c979")
        self.laps.tag_configure("invalid", foreground="#fa6868")
        self.laps.tag_configure("unknown", foreground="#aaaaaa")
        self.laps.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0,8))
        self.note = ttk.Label(self, text="Oturum türü oyun telemetrisinden alınamadığında 'Bilinmiyor' gösterilir.", style="Muted.TLabel")
        self.note.grid(row=5, column=0, sticky="w", padx=12, pady=5)
        self.refresh(True)

    def refresh(self, force=False):
        store = self.app.sessions
        if not force and store.version == self.version:
            return
        self.version = store.version
        sessions = store.recent(500)
        self.sessions_by_id = {str(s["id"]): s for s in sessions if s.get("id")}
        names = ["Tümü"] + sorted({s.get("game_name") or s.get("game_id") or "Bilinmiyor" for s in sessions})
        self.game_box["values"] = names
        if self.game.get() not in names:
            self.game.set("Tümü")
        fields = {
            "track": lambda s: s.get("track_name") or s.get("track_id") or "—",
            "car": lambda s: s.get("car_name") or s.get("car_id") or "—",
            "type": lambda s: s.get("session_type") or "Bilinmiyor",
            "date": lambda s: str(s.get("started") or "")[:10] or "—",
        }
        for key, (v, cb) in self.extra_filters.items():
            values = ["Tümü"] + sorted({fields[key](s) for s in sessions})
            cb["values"] = values
            if v.get() not in values:
                v.set("Tümü")
        selection = self.selected
        self.tree.delete(*self.tree.get_children())
        for s in sessions:
            game = s.get("game_name") or s.get("game_id") or "Bilinmiyor"
            if self.game.get() != "Tümü" and game != self.game.get():
                continue
            if any(v.get() != "Tümü" and v.get() != fields[key](s) for key, (v, _) in self.extra_filters.items()):
                continue
            sid = str(s["id"])
            count = s.get("laps_completed",0)
            valid = s.get("valid_laps",0)
            typ = s.get("session_type") or "Bilinmiyor"
            self.tree.insert("", "end", iid=sid, values=(s.get("started","—"), game,
                s.get("track_name") or s.get("track_id") or "—", s.get("car_name") or s.get("car_id") or "—",
                typ, duration(s), f"{valid}/{count}", fmt_ms(s["best_lap_ms"]) if s.get("best_lap_ms") else "—"))
        if selection in self.tree.get_children():
            self.tree.selection_set(selection)
            self.show_laps()
        else:
            self.selected = None
            self.laps.delete(*self.laps.get_children())

    def show_laps(self, event=None):
        chosen = self.tree.selection()
        if not chosen:
            return
        self.selected = chosen[0]
        s = self.sessions_by_id.get(self.selected, {})
        self.laps.delete(*self.laps.get_children())
        history = s.get("lap_history")
        if history:
            for lap in history:
                good = lap.get("valid")
                status = "Geçerli" if good else "Geçersiz"
                reason = lap.get("reason") or ("Doğrulandı" if lap.get("verified") else "Filtrelerle kabul edildi")
                self.laps.insert("", "end", values=(lap.get("number","—"), fmt_ms(lap["lap_ms"]) if lap.get("lap_ms") else "—", self._delta(lap.get("delta_previous_ms")), status, reason), tags=("valid" if good else "invalid",))
        else:
            for i, ms in enumerate(s.get("lap_times_ms", []), 1):
                self.laps.insert("", "end", values=(i, fmt_ms(ms), "—", "Eski kayıt", "Turun bireysel doğrulama bilgisi saklanmamış"), tags=("unknown",))
        self.note.config(text="Oturum: %s  |  Pist: %s  |  Araç: %s" % (s.get("session_type") or "Bilinmiyor", s.get("track_name") or "—", s.get("car_name") or "—"))

    @staticmethod
    def _delta(ms):
        if ms is None:
            return "—"
        return "%+.3f" % (ms / 1000.0)

    def tick(self, visible):
        if visible:
            self.refresh()
