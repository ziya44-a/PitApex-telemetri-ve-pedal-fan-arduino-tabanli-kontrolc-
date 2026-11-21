LOG = []
def showinfo(*a, **k): LOG.append(("info", a)); return "ok"
def showerror(*a, **k): LOG.append(("error", a)); return "ok"
def showwarning(*a, **k): LOG.append(("warn", a)); return "ok"
def askyesno(*a, **k): LOG.append(("yesno", a, k)); return True
