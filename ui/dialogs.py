"""Ayarlar penceresi ve 'tum verileri temizle' onay akisi."""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ui.themes import THEME_LABELS
from ui.i18n import apply_language

CONFIRM_WORDS = ("SİL", "SIL")        # Türkçe klavyede İ ile ya da I ile yazılabilir


class WipeDialog(tk.Toplevel):
    """1. aşama: ne silineceği yazılı, kullanıcı SİL yazmadan düğme pasif. İptal varsayılan odak.
    2. aşama: ayrı bir 'Son onay' kutusu (varsayılan cevap: Hayır)."""

    def __init__(self, parent, data_path, theme):
        super().__init__(parent)
        self.result = False
        c = theme.c
        self.configure(bg=c["bg"])
        self.title("Tüm verileri temizle")
        self.transient(parent)
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="⚠ Bu işlem geri alınamaz", style="Bad.TLabel", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(body, justify="left", wraplength=470, text=(
            "Şu klasördeki TÜM kullanıcı verileri kalıcı olarak silinecek:\n%s\n\n"
            "• Tur rekorları ve sektör rekorları\n"
            "• Oturum geçmişi ve istatistikleri\n"
            "• Tüm ayarlar ve tercihler (tema, pedal, fan)\n"
            "• Kayıtlı profiller\n"
            "• Yedekler\n\n"
            "Program dosyaları silinmez. Devam etmek için aşağıya SİL yazın." % data_path)).pack(anchor="w", pady=8)
        self.var = tk.StringVar()
        self.entry = ttk.Entry(body, textvariable=self.var, width=12)
        self.entry.pack(anchor="w")
        self.var.trace_add("write", self._changed)
        btns = ttk.Frame(body)
        btns.pack(anchor="e", pady=(14, 0), fill="x")
        self.ok = ttk.Button(btns, text="Verileri sil", style="Danger.TButton", command=self._stage2, state="disabled")
        self.ok.pack(side="right", padx=(8, 0))
        self.cancel = ttk.Button(btns, text="İPTAL", command=self.destroy, width=14)
        self.cancel.pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.destroy())      # Enter silme DEĞİL, iptal eder
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.cancel.focus_set()                              # varsayılan odak: İPTAL

    def _changed(self, *_):
        ok = self.var.get().strip() in CONFIRM_WORDS
        self.ok.config(state="normal" if ok else "disabled")

    def _stage2(self):
        if self.var.get().strip() not in CONFIRM_WORDS:
            return
        yes = messagebox.askyesno("Son onay", "Tüm PitApex kullanıcı verileri KALICI olarak silinecek.\n\n"
                                  "Emin misiniz?", icon="warning", default="no", parent=self)
        if yes:
            self.result = True
            self.destroy()


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        c = app.theme.c
        self.configure(bg=c["bg"])
        self.title("PitApex · Ayarlar")
        self.transient(parent)
        self.geometry("560x520")
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)

        tf = ttk.LabelFrame(body, text="Görünüm")
        tf.pack(fill="x", pady=4)
        self.theme_var = tk.StringVar(value=app.theme.name)
        for key, label in THEME_LABELS.items():
            ttk.Radiobutton(tf, text=label + " tema", value=key, variable=self.theme_var,
                            command=lambda: app.set_theme(self.theme_var.get())).pack(side="left", padx=10, pady=8)

        lf = ttk.LabelFrame(body, text="Dil")
        lf.pack(fill="x", pady=4)
        self.language_var = tk.StringVar(value=app.language)
        for key, label in (("tr", "Türkçe"), ("en", "İngilizce")):
            ttk.Radiobutton(lf, text=label, value=key, variable=self.language_var,
                            command=lambda: self.change_language()).pack(side="left", padx=10, pady=8)

        bf = ttk.LabelFrame(body, text="Ayar yedekleme / Settings backup")
        bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="JSON dışa aktar / Export", command=self.export_settings).pack(side="left", padx=8, pady=8)
        ttk.Button(bf, text="JSON içe aktar / Import", command=self.import_settings).pack(side="left", padx=8, pady=8)

        df = ttk.LabelFrame(body, text="Veri konumu")
        df.pack(fill="x", pady=4)
        ttk.Label(df, text=app.dm.root, wraplength=500, justify="left").pack(anchor="w", padx=8, pady=(6, 2))
        ttk.Button(df, text="Klasörü aç", command=self.open_folder).pack(anchor="w", padx=8, pady=(2, 8))
        msgs = []
        if app.dm.warning:
            msgs.append(app.dm.warning)
        for name, st in (("Rekor dosyası", app.records.status), ("Oturum dosyası", app.sessions.status),
                         ("Tercih dosyası", app.prefs.status)):
            if st == "restored":
                msgs.append("%s bozuktu, yedekten geri yüklendi." % name)
            elif st == "reset":
                msgs.append("%s bozuktu ve yedek bulunamadı: sıfırlandı (bozuk dosya yan tarafa saklandı)." % name)
            elif st == "write_error":
                msgs.append("%s yazılamadı. Disk dolu ya da klasör korumalı olabilir." % name)
        if msgs:
            ttk.Label(df, text="\n".join(msgs), style="Warn.TLabel", wraplength=500, justify="left").pack(
                anchor="w", padx=8, pady=(0, 8))

        ttk.Frame(body).pack(fill="both", expand=True)          # boşluk: tehlikeli bölüm hep en altta

        dz = ttk.LabelFrame(body, text="Tehlikeli İşlemler")
        dz.pack(fill="x", side="bottom", pady=(10, 0))
        ttk.Label(dz, text="Rekorlar, oturum geçmişi, ayarlar, profiller ve yedekler dahil bütün kullanıcı "
                           "verilerini siler. Geri alınamaz.", style="Muted.TLabel", wraplength=500, justify="left").pack(
            anchor="w", padx=8, pady=(6, 4))
        ttk.Button(dz, text="Tüm verilerimi temizle…", style="Danger.TButton", command=self.wipe).pack(
            anchor="w", padx=8, pady=(2, 10))

        apply_language(self, app.language)

    def export_settings(self):
        from storage.settings import export_configuration, PedalSettings
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", initialfile="PitApex-settings.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.app.pedals_page.save_settings()
            export_configuration(self.app.prefs, PedalSettings(self.app.dm), path)
            messagebox.showinfo("PitApex", "Ayarlar dışa aktarıldı / Settings exported", parent=self)
        except Exception as e:
            messagebox.showerror("PitApex", str(e), parent=self)

    def import_settings(self):
        from storage.settings import import_configuration, PedalSettings
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if not path:
            return
        if not messagebox.askyesno("PitApex", "Mevcut ayarlar değiştirilecek (tur kayıtları korunur). Devam?", parent=self):
            return
        try:
            import_configuration(self.app.prefs, PedalSettings(self.app.dm), path)
            self.app.apply_imported_settings()
            self.language_var.set(self.app.language)
            self.theme_var.set(self.app.theme.name)
            apply_language(self, self.app.language)
            messagebox.showinfo("PitApex", "Settings applied" if self.app.language == "en" else "Ayarlar yeniden başlatmadan uygulandı.", parent=self)
        except Exception as e:
            messagebox.showerror("PitApex", str(e), parent=self)

    def change_language(self):
        self.app.set_language(self.language_var.get())
        apply_language(self, self.app.language)
        self.title("PitApex · Settings" if self.app.language == "en" else "PitApex · Ayarlar")

    def open_folder(self):
        try:
            if os.name == "nt":
                os.startfile(self.app.dm.root)         # noqa: S606 - yerel klasör
        except Exception as e:
            messagebox.showinfo("PitApex", "Klasör açılamadı:\n%s" % e, parent=self)

    def wipe(self):
        dlg = WipeDialog(self, self.app.dm.root, self.app.theme)
        self.wait_window(dlg)
        if dlg.result:
            ok, msg = self.app.wipe_all()
            self.theme_var.set(self.app.theme.name)
            (messagebox.showinfo if ok else messagebox.showwarning)("PitApex", msg, parent=self)
