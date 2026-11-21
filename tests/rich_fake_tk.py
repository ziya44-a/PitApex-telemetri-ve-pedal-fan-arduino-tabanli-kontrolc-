"""Overlay testleri icin kayit tutan sahte tkinter alt kumesi (pencere nitelikleri, tuval ogeleri vb.)."""
import os
import re


class TclError(Exception):
    pass


class _W:
    def __init__(self, master=None, **kw):
        self.master = master
        self.cfg = dict(kw)
        self.attrs = {}
        self.binds = {}
        self.destroyed = False
        self.placed = False
        self._geom = None
        self.w, self.h = 760, 650
        self.items = []
        self.delete_calls = 0
        self.packed = True
        self.lift_calls = 0

    def configure(self, **kw): self.cfg.update(kw)
    config = configure
    def cget(self, k): return self.cfg.get(k)
    def attributes(self, name, value=None, *rest):
        if value is None and not rest:
            return self.attrs.get(name)
        self.attrs[name] = value
    def overrideredirect(self, *a): pass
    def title(self, *a): pass
    def protocol(self, *a): pass
    def deiconify(self): pass
    def update_idletasks(self): pass
    def pack(self, *a, **k): self.packed = True
    def pack_forget(self): self.packed = False
    def place(self, *a, **k): self.placed = True
    def place_forget(self): self.placed = False
    def lift(self, *a): self.lift_calls += 1
    def lower(self, *a): pass
    def bind(self, seq, fn=None, add=None): self.binds.setdefault(seq, []).append(fn)
    def geometry(self, g=None):
        if g is not None:
            self._geom = g
            m = re.match(r"(\d+)x(\d+)", g)
            if m:
                self.w, self.h = int(m.group(1)), int(m.group(2))
            return None
        return self._geom or "1x1+0+0"
    def winfo_width(self): return self.w
    def winfo_height(self): return self.h
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_id(self): return 1234
    def destroy(self): self.destroyed = True
    # Canvas
    def delete(self, *a):
        self.items.clear()
        self.delete_calls += 1
    def _add(self, kind, args, kw):
        self.items.append((kind, args, kw))
        return len(self.items)
    def create_rectangle(self, *a, **k): return self._add("rect", a, k)
    def create_line(self, *a, **k): return self._add("line", a, k)
    def create_text(self, *a, **k): return self._add("text", a, k)
    def create_polygon(self, *a, **k): return self._add("poly", a, k)
    def create_oval(self, *a, **k): return self._add("oval", a, k)
    def create_image(self, *a, **k): return self._add("image", a, k)

    def kinds(self, kind):
        return [i for i in self.items if i[0] == kind]


class Toplevel(_W): pass
class Label(_W): pass
class Canvas(_W): pass
class Scale(_W): pass


class PhotoImage:
    def __init__(self, master=None, file=None, **kw):
        if file is None or not os.path.isfile(file):
            raise TclError("couldn't open \"%s\": no such file or directory" % file)
        self.file = file
