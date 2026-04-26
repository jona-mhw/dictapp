"""Popup 'What's New' al abrir tras actualizar."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .theme import PALETTE
from .version import WHATS_NEW, VERSION


def should_show(last_seen: str) -> bool:
    return last_seen != VERSION


def show(parent: tk.Tk) -> None:
    win = tk.Toplevel(parent)
    win.title(f"Novedades — v{VERSION}")
    win.configure(bg=PALETTE["bg"])
    win.geometry("560x620")
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()

    # encabezado
    header = ttk.Frame(win, style="TFrame")
    header.pack(fill=tk.X, padx=24, pady=(24, 8))

    ttk.Label(header, text=WHATS_NEW["title"], style="Title.TLabel",
              font=("Segoe UI Semibold", 18)).pack(anchor="w")
    ttk.Label(header, text=WHATS_NEW["tagline"], style="Subtitle.TLabel",
              font=("Segoe UI", 10, "italic")).pack(anchor="w", pady=(2, 0))

    ttk.Separator(win, orient="horizontal").pack(fill=tk.X, padx=24, pady=12)

    # canvas con scroll para las secciones
    canvas = tk.Canvas(win, bg=PALETTE["bg"], highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas, style="TFrame")
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(24, 0))
    scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

    def _resize(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(body_id, width=canvas.winfo_width())
    body.bind("<Configure>", _resize)
    canvas.bind("<Configure>", _resize)

    def _wheel(event):
        canvas.yview_scroll(int(-event.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _wheel)

    # secciones
    for sec in WHATS_NEW["sections"]:
        card = ttk.Frame(body, style="Card.TFrame")
        card.pack(fill=tk.X, pady=8, padx=4)
        title = f"  {sec['icon']}   {sec['title']}"
        ttk.Label(card, text=title, style="Card.TLabel",
                  font=("Segoe UI Semibold", 11),
                  background=PALETTE["bg_card"]).pack(anchor="w", padx=14, pady=(10, 4))
        for item in sec["items"]:
            ttk.Label(card, text=f"   •  {item}", style="Card.TLabel",
                      background=PALETTE["bg_card"],
                      foreground=PALETTE["fg"],
                      wraplength=470,
                      justify="left").pack(anchor="w", padx=14, pady=2)
        tk.Frame(card, bg=PALETTE["bg_card"], height=10).pack()

    # qué probar
    try_card = ttk.Frame(body, style="Card.TFrame")
    try_card.pack(fill=tk.X, pady=(14, 8), padx=4)
    ttk.Label(try_card, text="   ▶   Pruébalo así",
              background=PALETTE["bg_card"],
              foreground=PALETTE["accent"],
              font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=14, pady=(10, 4))
    for line in WHATS_NEW["try_this"]:
        ttk.Label(try_card, text=f"   {line}", style="Card.TLabel",
                  background=PALETTE["bg_card"],
                  foreground=PALETTE["fg"],
                  wraplength=470,
                  justify="left").pack(anchor="w", padx=14, pady=2)
    tk.Frame(try_card, bg=PALETTE["bg_card"], height=10).pack()

    # footer
    footer = ttk.Frame(win, style="TFrame")
    footer.pack(fill=tk.X, padx=24, pady=12)
    close_btn = ttk.Button(footer, text="¡A dictar!", style="Accent.TButton",
                           command=win.destroy)
    close_btn.pack(side=tk.RIGHT)

    win.bind("<Escape>", lambda *_: win.destroy())
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.update_idletasks()
    # centrar
    parent.update_idletasks()
    px = parent.winfo_rootx() + parent.winfo_width() // 2 - win.winfo_width() // 2
    py = parent.winfo_rooty() + parent.winfo_height() // 2 - win.winfo_height() // 2
    win.geometry(f"+{max(px, 0)}+{max(py, 0)}")
    close_btn.focus_set()
