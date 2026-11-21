"""PitApex girisi."""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk  # noqa: E402
from tkinter import messagebox  # noqa: E402


def _log(dm_root, text):
    try:
        with open(os.path.join(dm_root, "pitapex_hata.log"), "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
    except Exception:
        pass


def main():
    from storage.data_manager import DataManager
    from storage.paths import app_dir

    root = tk.Tk()
    root.withdraw()
    try:
        dm = DataManager()
    except Exception as e:
        messagebox.showerror("PitApex", "Veri klasörü oluşturulamadı:\n%s" % e)
        return
    base = app_dir()
    dm.migrate_legacy([base, os.path.join(os.path.dirname(base), "PedalHaptic"),
                       os.path.join(base, "PedalHaptic")])      # eski surumun ayar/profil klasorleri

    def on_error(exc, val, tb):
        _log(dm.root, "".join(traceback.format_exception(exc, val, tb)))

    root.report_callback_exception = on_error
    try:
        from ui.main_window import App
        root.geometry("1100x900")
        root.minsize(980, 640)
        App(root, dm)
        root.deiconify()
    except Exception:
        _log(dm.root, traceback.format_exc())
        messagebox.showerror("PitApex", "PitApex başlatılamadı.\nAyrıntı: %s" % os.path.join(dm.root, "pitapex_hata.log"))
        return
    root.mainloop()


if __name__ == "__main__":
    main()
