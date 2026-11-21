"""04 - Kaydedilen Rekorlar: Oyun -> Pist -> Arac modeli."""
import tkinter as tk
from tkinter import ttk

from core.models import fmt_ms


class RecordsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._ver = None
        self.build()
        self.refresh()

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Label(top, text="Kaydedilen Rekorlar", style="Big.TLabel").pack(side="left")
        ttk.Button(top, text="Yenile", command=lambda: self.refresh(force=True)).pack(side="right")
        self.empty_lbl = ttk.Label(top, text="", style="Muted.TLabel")
        self.empty_lbl.pack(side="left", padx=12)

        cols = ("lap", "s1", "s2", "s3", "date", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Oyun  ›  Pist  ›  Araç modeli")
        for k, t, w in (("lap", "En iyi tur", 100), ("s1", "S1", 90), ("s2", "S2", 90), ("s3", "S3", 90),
                        ("date", "Kayıt tarihi", 150), ("status", "Durum", 130)):
            self.tree.heading(k, text=t)
            self.tree.column(k, width=w, anchor="center")
        self.tree.column("#0", width=380)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=4)
        sb.grid(row=1, column=1, sticky="ns", pady=4)
        ttk.Label(self, text="Doğrulanmamış: oyun tur geçerliliğini bildirmediği için kayıt, pit turu/pist dışı filtreleriyle "
                             "yazıldı. Sektör süreleri oyundan doğrulanabildiğinde saklanır; aksi halde “—” görünür.",
                  style="Muted.TLabel", wraplength=900, justify="left").grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))

    def refresh(self, force=False):
        store = self.app.records
        if not force and self._ver == store.version:
            return
        self._ver = store.version
        self.tree.delete(*self.tree.get_children())
        recs = store.all_records()
        self.empty_lbl.config(text="" if recs else "Henüz kayıt yok. Desteklenen oyunlarda geçerli turlar otomatik kaydedilir.")
        gnodes, tnodes = {}, {}
        for game, track, car, r in recs:
            if game not in gnodes:
                gnodes[game] = self.tree.insert("", "end", text=game, open=True)
            tk_ = (game, track)
            if tk_ not in tnodes:
                tnodes[tk_] = self.tree.insert(gnodes[game], "end", text=track, open=True)
            dash = lambda v: fmt_ms(v) if v is not None else "—"
            self.tree.insert(tnodes[tk_], "end", text=car,
                             values=(fmt_ms(r["lap_ms"]), dash(r.get("s1_ms")), dash(r.get("s2_ms")),
                                     dash(r.get("s3_ms")), (r.get("date") or "—"),
                                     "Doğrulanmış" if r.get("verified") else "Doğrulanmamış"))

    def _all_items(self):
        out, stack = [], list(self.tree.get_children())
        while stack:
            i = stack.pop()
            out.append(i)
            stack.extend(self.tree.get_children(i))
        return out

    def tick(self, visible):
        if visible:
            self.refresh()
