"""Ventana flotante con eventos + transcripciones."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import scrolledtext, ttk

from .theme import PALETTE
from .version import APP_NAME


class LogWindow:
    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.win: tk.Toplevel | None = None
        self.events_widget: scrolledtext.ScrolledText | None = None
        self.transcripts_widget: scrolledtext.ScrolledText | None = None
        # buffers para conservar contenido entre aperturas
        self._events_buffer: list[str] = []
        self._transcripts_buffer: list[str] = []

    @property
    def is_open(self) -> bool:
        return self.win is not None and bool(self.win.winfo_exists())

    def toggle(self) -> None:
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        if self.is_open:
            self.win.lift()  # type: ignore[union-attr]
            self.win.focus_force()  # type: ignore[union-attr]
            return
        win = tk.Toplevel(self.parent)
        self.win = win
        win.title(f"{APP_NAME} — Log y transcripciones")
        win.configure(bg=PALETTE["bg"])
        win.geometry("640x520")
        win.protocol("WM_DELETE_WINDOW", self.close)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ev_tab = ttk.Frame(nb, style="TFrame")
        nb.add(ev_tab, text="  Eventos  ")
        self.events_widget = scrolledtext.ScrolledText(
            ev_tab, wrap=tk.WORD, state="disabled",
            bg=PALETTE["bg_alt"], fg=PALETTE["fg"],
            insertbackground=PALETTE["fg"],
            relief="flat", borderwidth=0,
            font=("Consolas", 9),
        )
        self.events_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._flush(self.events_widget, self._events_buffer)

        tr_tab = ttk.Frame(nb, style="TFrame")
        nb.add(tr_tab, text="  Transcripciones  ")
        self.transcripts_widget = scrolledtext.ScrolledText(
            tr_tab, wrap=tk.WORD, state="disabled",
            bg=PALETTE["bg_alt"], fg=PALETTE["fg"],
            insertbackground=PALETTE["fg"],
            relief="flat", borderwidth=0,
            font=("Segoe UI", 10),
        )
        self.transcripts_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._flush(self.transcripts_widget, self._transcripts_buffer)

        # botón limpiar
        bottom = ttk.Frame(win, style="TFrame")
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(bottom, text="Limpiar eventos", command=self.clear_events
                   ).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Limpiar transcripciones", command=self.clear_transcripts
                   ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bottom, text="Cerrar", command=self.close
                   ).pack(side=tk.RIGHT)

    def close(self) -> None:
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        self.events_widget = None
        self.transcripts_widget = None

    # ----- API -----
    def log_event(self, message: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        self._events_buffer.append(line)
        if self.events_widget is not None:
            self._append(self.events_widget, line)

    def log_transcript(self, text: str, backend: str, seconds: float) -> None:
        ts = time.strftime("%H:%M:%S")
        block = f"[{ts}] ({backend} · {seconds:.1f}s)\n{text}\n\n"
        self._transcripts_buffer.append(block)
        if self.transcripts_widget is not None:
            self._append(self.transcripts_widget, block, newline=False)

    def clear_events(self) -> None:
        self._events_buffer.clear()
        if self.events_widget is not None:
            self.events_widget.config(state="normal")
            self.events_widget.delete("1.0", tk.END)
            self.events_widget.config(state="disabled")

    def clear_transcripts(self) -> None:
        self._transcripts_buffer.clear()
        if self.transcripts_widget is not None:
            self.transcripts_widget.config(state="normal")
            self.transcripts_widget.delete("1.0", tk.END)
            self.transcripts_widget.config(state="disabled")

    # ----- internos -----
    @staticmethod
    def _append(widget: scrolledtext.ScrolledText, text: str, newline: bool = True) -> None:
        widget.config(state="normal")
        widget.insert(tk.END, text + ("\n" if newline else ""))
        widget.see(tk.END)
        widget.config(state="disabled")

    def _flush(self, widget: scrolledtext.ScrolledText, buffer: list[str]) -> None:
        widget.config(state="normal")
        for line in buffer:
            widget.insert(tk.END, line if line.endswith("\n") else line + "\n")
        widget.see(tk.END)
        widget.config(state="disabled")
