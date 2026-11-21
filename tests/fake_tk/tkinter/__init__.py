"""Sadece duman testi icin sahte tkinter: widget'lar config degerlerini saklar, hicbir sey cizmez."""
import itertools

_ids = itertools.count(1)


class Widget:
    def __init__(self, master=None, **kw):
        self.master = master
        self._cfg = dict(kw)
        self._rows = 0
        self._cols = 0
        self._children = []
        self._tree = {}
        self.calls = []
        if master is not None and hasattr(master, "_children"):
            master._children.append(self)

    def grid(self, **kw):
        if "grid_remove" in self.calls[-1:]:
            self.calls.append("grid_show")
        if self.master is not None and hasattr(self.master, "_rows"):
            r = kw.get("row", 0) + kw.get("rowspan", 1)
            self.master._rows = max(self.master._rows, r)
            c = kw.get("column", 0) + kw.get("columnspan", 1)
            self.master._cols = max(self.master._cols, c)

    def grid_size(self):
        return (self._cols, self._rows)

    def pack(self, *a, **k): pass
    def grid_remove(self): self.calls.append("grid_remove")
    def pack_forget(self): pass
    def create_window(self, *a, **k): return 1
    def itemconfigure(self, *a, **k): pass
    def bbox(self, *a): return (0, 0, 10, 10)
    def yview_scroll(self, *a): pass
    def bind_all(self, *a, **k): pass
    def unbind_all(self, *a, **k): pass
    def place(self, *a, **k): pass
    def columnconfigure(self, *a, **k): pass
    def rowconfigure(self, *a, **k): pass
    def config(self, **kw): self._cfg.update(kw)
    configure = config
    def __setitem__(self, k, v): self._cfg[k] = v
    def __getitem__(self, k): return self._cfg.get(k)
    def tkraise(self): self.calls.append("tkraise")
    def bind(self, *a, **k): pass
    def after(self, *a, **k): pass
    def title(self, *a): pass
    def geometry(self, *a): pass
    def minsize(self, *a): pass
    def iconbitmap(self, *a): pass
    def protocol(self, *a): pass
    def option_add(self, *a): pass
    def transient(self, *a): pass
    def resizable(self, *a): pass
    def grab_set(self): pass
    def wait_visibility(self): pass
    def focus_set(self): pass
    def withdraw(self): pass
    def deiconify(self): pass
    def destroy(self):
        self.calls.append("destroy")
        m = self.master
        if m is not None and hasattr(m, "_children") and self in m._children:
            m._children.remove(self)

    def winfo_children(self): return list(self._children)
    def winfo_exists(self): return 1
    def tab(self, *a, **k): pass
    def tag_configure(self, *a, **k): pass
    def delete(self, *a): pass
    def mainloop(self): pass
    def wait_window(self, w): pass
    def current(self, *a): pass
    def add(self, *a, **k): pass
    def place_forget(self): pass
    def lift(self, *a): pass
    def lower(self, *a): pass
    def attributes(self, *a): pass
    def overrideredirect(self, *a): pass
    def after_cancel(self, *a): pass
    def winfo_width(self): return 760
    def winfo_height(self): return 650
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_id(self): return 1
    def create_rectangle(self, *a, **k): pass
    def create_polygon(self, *a, **k): pass
    def create_image(self, *a, **k): pass
    # Canvas
    def delete(self, *a): pass
    def create_line(self, *a, **k): pass
    def create_text(self, *a, **k): pass
    def create_oval(self, *a, **k): pass
    # Treeview
    def heading(self, *a, **k): pass
    def column(self, *a, **k): pass
    def yview(self, *a): pass
    def set(self, *a): pass
    def insert(self, parent, index, **kw):
        i = "I%d" % next(_ids)
        self._tree[i] = (parent, kw)
        return i
    def get_children(self, item=None): return []
    def item(self, *a, **k): return {}


class TclError(Exception): pass


class Tk(Widget): pass
class Toplevel(Widget): pass
class Frame(Widget): pass
class Label(Widget): pass
class Canvas(Widget): pass
class Scale(Widget): pass
class PhotoImage(Widget): pass


class _Var:
    def __init__(self, master=None, value=None, **kw): self._v = value
    def get(self): return self._v
    def set(self, v): self._v = v
    def trace_add(self, *a): pass


class StringVar(_Var):
    def __init__(self, master=None, value=""): self._v = value


class IntVar(_Var):
    def __init__(self, master=None, value=0): self._v = value


class DoubleVar(_Var):
    def __init__(self, master=None, value=0.0): self._v = value


class BooleanVar(_Var):
    def __init__(self, master=None, value=False): self._v = value
