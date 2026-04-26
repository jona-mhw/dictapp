"""Tema oscuro minimalista para ttk."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTE = {
    "bg":         "#1e1f24",
    "bg_alt":     "#262830",
    "bg_card":    "#2d2f37",
    "fg":         "#e6e6ea",
    "fg_dim":     "#a0a3ad",
    "accent":     "#7c5cff",
    "accent_hi":  "#9d83ff",
    "ok":         "#3ddc84",
    "warn":       "#f5b942",
    "err":        "#ff6b6b",
    "border":     "#3a3d47",
}


def apply_dark_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    p = PALETTE
    root.configure(bg=p["bg"])

    style.configure(".",
                    background=p["bg"],
                    foreground=p["fg"],
                    fieldbackground=p["bg_alt"],
                    bordercolor=p["border"],
                    lightcolor=p["bg_alt"],
                    darkcolor=p["bg"],
                    troughcolor=p["bg_alt"],
                    focuscolor=p["accent"],
                    selectbackground=p["accent"],
                    selectforeground="#ffffff",
                    insertcolor=p["fg"],
                    font=("Segoe UI", 10))

    style.configure("TFrame", background=p["bg"])
    style.configure("Card.TFrame", background=p["bg_card"])
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("Card.TLabel", background=p["bg_card"], foreground=p["fg"])
    style.configure("Dim.TLabel", background=p["bg"], foreground=p["fg_dim"])
    style.configure("Title.TLabel", background=p["bg"], foreground=p["fg"], font=("Segoe UI Semibold", 14))
    style.configure("Subtitle.TLabel", background=p["bg"], foreground=p["fg_dim"], font=("Segoe UI", 9))
    style.configure("Status.TLabel", background=p["bg"], foreground=p["fg_dim"], font=("Segoe UI", 9))

    style.configure("TButton",
                    background=p["bg_alt"],
                    foreground=p["fg"],
                    bordercolor=p["border"],
                    padding=(12, 6),
                    relief="flat")
    style.map("TButton",
              background=[("active", p["bg_card"]), ("pressed", p["bg_card"])],
              foreground=[("disabled", p["fg_dim"])])

    style.configure("Accent.TButton",
                    background=p["accent"],
                    foreground="#ffffff",
                    padding=(14, 8),
                    relief="flat",
                    font=("Segoe UI Semibold", 10))
    style.map("Accent.TButton",
              background=[("active", p["accent_hi"]), ("pressed", p["accent_hi"])])

    style.configure("Danger.TButton",
                    background=p["err"],
                    foreground="#ffffff",
                    padding=(14, 8),
                    relief="flat",
                    font=("Segoe UI Semibold", 10))
    style.map("Danger.TButton",
              background=[("active", "#ff8585"), ("pressed", "#ff8585")])

    style.configure("TCheckbutton", background=p["bg"], foreground=p["fg"])
    style.map("TCheckbutton",
              background=[("active", p["bg"])])
    style.configure("TRadiobutton", background=p["bg"], foreground=p["fg"])
    style.map("TRadiobutton",
              background=[("active", p["bg"])])

    style.configure("TEntry",
                    fieldbackground=p["bg_alt"],
                    foreground=p["fg"],
                    bordercolor=p["border"],
                    insertcolor=p["fg"])
    style.configure("TCombobox",
                    fieldbackground=p["bg_alt"],
                    background=p["bg_alt"],
                    foreground=p["fg"],
                    arrowcolor=p["fg"],
                    bordercolor=p["border"])
    style.map("TCombobox",
              fieldbackground=[("readonly", p["bg_alt"])],
              foreground=[("readonly", p["fg"])])
    root.option_add("*TCombobox*Listbox.background", p["bg_alt"])
    root.option_add("*TCombobox*Listbox.foreground", p["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    style.configure("TNotebook", background=p["bg"], borderwidth=0)
    style.configure("TNotebook.Tab",
                    background=p["bg_alt"],
                    foreground=p["fg_dim"],
                    padding=(14, 6),
                    borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", p["bg_card"])],
              foreground=[("selected", p["fg"])])

    style.configure("TSeparator", background=p["border"])
    style.configure("Horizontal.TProgressbar",
                    background=p["accent"],
                    troughcolor=p["bg_alt"],
                    bordercolor=p["bg"])
