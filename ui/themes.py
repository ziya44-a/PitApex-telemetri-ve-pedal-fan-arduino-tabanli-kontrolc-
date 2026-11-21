"""Siyah / beyaz tema. Siyah temanin arka plan rengi eski uygulamadaki (#121212) ile AYNI; dugmeler turuncu."""
from tkinter import ttk

THEMES = {
    "dark": {
        "bg": "#121212", "panel": "#1c1c1c", "panel2": "#262626", "hover": "#333333", "border": "#333333",
        "fg": "#e8e8e8", "muted": "#9a9a9a", "accent": "#ff8c1a", "accent_hover": "#ffa64d",
        "on_accent": "#000000", "ind_off": "#2a2a2a", "live": "#3ddc84", "saved": "#7fb2ff",
        "ok": "#3ddc84", "warn": "#ffb020", "bad": "#ff5c5c", "danger": "#c0392b",
    },
    "light": {
        "bg": "#f3f3f3", "panel": "#ffffff", "panel2": "#e3e3e3", "hover": "#d4d4d4", "border": "#c8c8c8",
        "fg": "#1a1a1a", "muted": "#666666", "accent": "#ff8c1a", "accent_hover": "#ffa64d",
        "on_accent": "#000000", "ind_off": "#dcdcdc", "live": "#13803f", "saved": "#2058b8",
        "ok": "#13803f", "warn": "#b36b00", "bad": "#c62828", "danger": "#c0392b",
    },
}
THEME_LABELS = {"dark": "Siyah", "light": "Beyaz"}


class Theme:
    def __init__(self, name="dark"):
        self.name = name if name in THEMES else "dark"
        self.listeners = []

    @property
    def c(self):
        return THEMES[self.name]

    def on_change(self, fn):
        self.listeners.append(fn)

    def set(self, name, root):
        if name not in THEMES:
            return
        self.name = name
        self.apply(root)
        for fn in list(self.listeners):
            try:
                fn()
            except Exception:
                pass

    def apply(self, root):
        c = self.c
        root.configure(bg=c["bg"])
        st = ttk.Style(root)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["panel"],
                     bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"], troughcolor=c["panel"])
        st.configure("TFrame", background=c["bg"])
        st.configure("TLabel", background=c["bg"], foreground=c["fg"])
        st.configure("TLabelframe", background=c["bg"], bordercolor=c["border"])
        st.configure("TLabelframe.Label", background=c["bg"], foreground=c["muted"])
        # dugmeler: turuncu
        st.configure("TButton", background=c["accent"], foreground=c["on_accent"], bordercolor=c["accent"],
                     padding=5, focuscolor=c["accent"])
        st.map("TButton", background=[("active", c["accent_hover"]), ("disabled", c["panel2"])],
               foreground=[("disabled", c["muted"])])
        st.configure("Danger.TButton", background=c["danger"], foreground="#ffffff", bordercolor=c["danger"],
                     padding=5)
        st.map("Danger.TButton", background=[("active", "#e04a38"), ("disabled", c["panel2"])],
               foreground=[("disabled", c["muted"])])
        st.configure("TCheckbutton", background=c["bg"], foreground=c["fg"])
        st.map("TCheckbutton", background=[("active", c["bg"])],
               indicatorcolor=[("selected", c["accent"]), ("!selected", c["panel2"])])
        st.configure("TRadiobutton", background=c["bg"], foreground=c["fg"])
        st.map("TRadiobutton", background=[("active", c["bg"])],
               indicatorcolor=[("selected", c["accent"]), ("!selected", c["panel2"])])
        st.configure("Toolbutton", background=c["panel2"], foreground=c["fg"], padding=6, bordercolor=c["border"])
        st.map("Toolbutton", background=[("selected", c["accent"]), ("active", c["hover"])],
               foreground=[("selected", c["on_accent"])])
        st.configure("Tab.Toolbutton", background=c["panel2"], foreground=c["fg"], padding=(16, 8),
                     bordercolor=c["border"], font=("Segoe UI", 10, "bold"))
        st.map("Tab.Toolbutton", background=[("selected", c["accent"]), ("active", c["hover"])],
               foreground=[("selected", c["on_accent"])])
        st.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["panel"],
                     bordercolor=c["panel"], lightcolor=c["accent"], darkcolor=c["accent"])
        st.configure("Horizontal.TScale", background=c["bg"], troughcolor=c["panel2"], bordercolor=c["bg"],
                     lightcolor=c["bg"], darkcolor=c["bg"])
        for w in ("TCombobox", "TSpinbox", "TEntry"):
            st.configure(w, fieldbackground=c["panel"], background=c["panel2"], foreground=c["fg"],
                         arrowcolor=c["fg"], bordercolor=c["border"], insertcolor=c["fg"])
        st.map("TCombobox", fieldbackground=[("readonly", c["panel"])], foreground=[("readonly", c["fg"])],
               selectbackground=[("readonly", c["panel"])], selectforeground=[("readonly", c["fg"])])
        root.option_add("*TCombobox*Listbox.background", c["panel"])
        root.option_add("*TCombobox*Listbox.foreground", c["fg"])
        root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        root.option_add("*TCombobox*Listbox.selectForeground", c["on_accent"])
        # tablo
        st.configure("Treeview", background=c["panel"], fieldbackground=c["panel"], foreground=c["fg"],
                     bordercolor=c["border"], rowheight=24)
        st.map("Treeview", background=[("selected", c["accent"])], foreground=[("selected", c["on_accent"])])
        st.configure("Treeview.Heading", background=c["panel2"], foreground=c["fg"], bordercolor=c["border"],
                     padding=4)
        st.map("Treeview.Heading", background=[("active", c["hover"])])
        # etiket turleri
        st.configure("Muted.TLabel", foreground=c["muted"])
        st.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        st.configure("Big.TLabel", font=("Segoe UI", 12, "bold"))
        st.configure("Live.TLabel", foreground=c["fg"])
        st.configure("Saved.TLabel", foreground=c["saved"], font=("Segoe UI", 9, "italic"))
        st.configure("NA.TLabel", foreground=c["muted"])
        st.configure("LiveDot.TLabel", foreground=c["live"])
        st.configure("SavedDot.TLabel", foreground=c["saved"])
        for k in ("ok", "warn", "bad"):
            st.configure("%s.TLabel" % k.capitalize(), foreground=c[k])
        st.configure("Warn.TLabel", foreground=c["warn"])
