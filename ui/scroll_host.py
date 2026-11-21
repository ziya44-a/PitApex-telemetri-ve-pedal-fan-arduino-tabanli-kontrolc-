"""Reusable vertical scrolling host for non-pedal pages."""
import tkinter as tk
from tkinter import ttk

class ScrollHost(ttk.Frame):
    def __init__(self, parent, background):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=background)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar.grid(row=0, column=1, sticky="ns")
        self.body = ttk.Frame(self.canvas)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self._job = None
        self.body.bind("<Configure>", self._queue)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<Enter>", self._enter)
        self.canvas.bind("<Leave>", self._leave)

    def _queue(self, event=None):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(70, self._update)

    def _update(self):
        self._job = None
        if self.canvas.winfo_exists():
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        self._queue()

    def _enter(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", self._wheel)
        self.canvas.bind_all("<Button-5>", self._wheel)

    def _leave(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _wheel(self, event):
        if event.num == 4:
            amount = -3
        elif event.num == 5:
            amount = 3
        else:
            amount = -int(event.delta / 120) if event.delta else 0
        if amount:
            self.canvas.yview_scroll(amount, "units")
