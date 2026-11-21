from tkinter import Widget


class Style:
    def __init__(self, *a, **k): pass
    def theme_use(self, *a): pass
    def configure(self, *a, **k): pass
    def map(self, *a, **k): pass


for _n in ("Frame", "Label", "LabelFrame", "Button", "Checkbutton", "Radiobutton", "Combobox", "Entry",
           "Scale", "Spinbox", "Progressbar", "Scrollbar", "Treeview", "Notebook"):
    globals()[_n] = type(_n, (Widget,), {})
