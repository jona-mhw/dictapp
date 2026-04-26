"""Ventana principal con tema oscuro, pestañas y modo compacto."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from . import audio
from .audio_sd import SDMeterScanner, SD_AVAILABLE
from .mic_meter import MultiMicMeter
from .theme import PALETTE
from .version import APP_NAME, VERSION


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        config,
        on_toggle_recording: Callable[[], None],
        on_change_service: Callable[[str], None],
        on_change_groq_key: Callable[[str | None], None],
        on_change_hotkey: Callable[[str], tuple[bool, str]],
        on_change_local_model: Callable[[str], None],
        on_change_local_device: Callable[[str], None],
        on_change_mic: Callable[[int], None],
        on_change_setting: Callable[[str, object], None],
        on_warm_up_local: Callable[[], None],
        on_toggle_log: Callable[[], None],
        on_change_ffmpeg_device: Callable[[str], None] | None = None,
        list_ffmpeg_devices: Callable[[], list] | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.config = config
        self._mic_meter: MultiMicMeter | None = None
        self._mic_widgets: list[dict] = []  # filas con bar/canvas/label/radio
        self._on_toggle_recording = on_toggle_recording
        self._on_change_service = on_change_service
        self._on_change_groq_key = on_change_groq_key
        self._on_change_hotkey = on_change_hotkey
        self._on_change_local_model = on_change_local_model
        self._on_change_local_device = on_change_local_device
        self._on_change_mic = on_change_mic
        self._on_change_setting = on_change_setting
        self._on_warm_up_local = on_warm_up_local
        self._on_toggle_log = on_toggle_log
        self._on_change_ffmpeg_device = on_change_ffmpeg_device or (lambda _name: None)
        self._list_ffmpeg_devices = list_ffmpeg_devices or (lambda: [])
        self._on_close = on_close or (lambda: None)

        self._build()

    # ---------------------------------------------------------------- build
    def _build(self) -> None:
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry("520x640")
        self.root.minsize(440, 520)
        self.root.configure(bg=PALETTE["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.attributes("-topmost", bool(self.config.get("always_on_top")))

        # contenedor de modo normal
        self.normal_frame = ttk.Frame(self.root, style="TFrame")
        self._build_normal(self.normal_frame)

        # contenedor de modo compacto
        self.compact_frame = ttk.Frame(self.root, style="Card.TFrame")
        self._build_compact(self.compact_frame)

        self._apply_compact(bool(self.config.get("compact_mode", False)))

    def _build_normal(self, outer: ttk.Frame) -> None:
        # encabezado
        header = ttk.Frame(outer, style="TFrame")
        header.pack(fill=tk.X, padx=14, pady=(12, 0))
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text=f"  v{VERSION}", style="Subtitle.TLabel").pack(side=tk.LEFT, pady=(6, 0))
        self.compact_btn = ttk.Button(header, text="Modo compacto", command=self._toggle_compact)
        self.compact_btn.pack(side=tk.RIGHT)
        self.log_btn = ttk.Button(header, text="Mostrar log", command=self._on_toggle_log)
        self.log_btn.pack(side=tk.RIGHT, padx=(0, 6))

        # tarjeta principal
        main_card = ttk.Frame(outer, style="Card.TFrame")
        main_card.pack(fill=tk.X, padx=14, pady=(12, 8))
        inner = ttk.Frame(main_card, style="Card.TFrame")
        inner.pack(fill=tk.X, padx=16, pady=14)

        self.record_btn = ttk.Button(inner, text="● Iniciar grabación",
                                     style="Accent.TButton",
                                     command=self._on_toggle_recording)
        self.record_btn.pack(fill=tk.X)

        status_row = ttk.Frame(inner, style="Card.TFrame")
        status_row.pack(fill=tk.X, pady=(10, 0))
        self.status_dot = tk.Canvas(status_row, width=14, height=14,
                                    bg=PALETTE["bg_card"], highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT)
        self._draw_dot(PALETTE["fg_dim"])
        self.status_label = ttk.Label(status_row, text="Inactivo",
                                      style="Card.TLabel",
                                      background=PALETTE["bg_card"],
                                      foreground=PALETTE["fg"])
        self.status_label.pack(side=tk.LEFT, padx=(8, 0))
        self.hotkey_hint = ttk.Label(status_row,
                                     text=f"Atajo: {self.config.get('hotkey').upper()}",
                                     style="Card.TLabel",
                                     background=PALETTE["bg_card"],
                                     foreground=PALETTE["fg_dim"])
        self.hotkey_hint.pack(side=tk.RIGHT)

        # pestañas
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(8, 4))
        self._build_tab_general()
        self._build_tab_settings()

        footer = ttk.Frame(outer, style="TFrame")
        footer.pack(fill=tk.X, padx=14, pady=(6, 12))
        self.service_status_label = ttk.Label(footer, text="", style="Status.TLabel",
                                              wraplength=480, justify="left")
        self.service_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _build_compact(self, frame: ttk.Frame) -> None:
        inner = ttk.Frame(frame, style="Card.TFrame")
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.compact_record_btn = ttk.Button(inner, text="● Grabar",
                                             style="Accent.TButton",
                                             command=self._on_toggle_recording)
        self.compact_record_btn.pack(fill=tk.X)
        row = ttk.Frame(inner, style="Card.TFrame")
        row.pack(fill=tk.X, pady=(6, 0))
        self.compact_status = ttk.Label(row, text="Inactivo",
                                        style="Card.TLabel",
                                        background=PALETTE["bg_card"],
                                        foreground=PALETTE["fg_dim"])
        self.compact_status.pack(side=tk.LEFT)
        ttk.Button(row, text="↺", width=3, command=self._toggle_compact).pack(side=tk.RIGHT)

    # ----------------------------------------------------------------- tabs
    def _build_tab_general(self) -> None:
        tab = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(tab, text="  General  ")

        ttk.Label(tab, text="Servicio de transcripción",
                  style="Subtitle.TLabel").pack(anchor="w", padx=10, pady=(12, 4))
        self.service_var = tk.StringVar(value=self.config.get("service"))
        for opt in ("Whisper (Groq)", "Google", "Whisper local"):
            ttk.Radiobutton(tab, text=opt, value=opt, variable=self.service_var,
                            command=lambda: self._on_change_service(self.service_var.get())
                            ).pack(anchor="w", padx=14, pady=2)

        ttk.Separator(tab).pack(fill=tk.X, padx=10, pady=10)

        mic_header = ttk.Frame(tab, style="TFrame")
        mic_header.pack(fill=tk.X, padx=10, pady=(0, 0))
        ttk.Label(mic_header,
                  text="Micrófono — habla unos segundos; el scanner rota por todos",
                  style="Subtitle.TLabel").pack(side=tk.LEFT)
        ttk.Button(mic_header, text="↻", width=3, command=self.refresh_microphones
                   ).pack(side=tk.RIGHT)

        self.mic_list_frame = ttk.Frame(tab, style="TFrame")
        self.mic_list_frame.pack(fill=tk.X, padx=10, pady=(4, 8))
        self.mic_var = tk.IntVar(value=int(self.config.get("mic_index", -1)))
        self.refresh_microphones()

        ttk.Separator(tab).pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(tab, text="Whisper local", style="Subtitle.TLabel").pack(anchor="w", padx=10)
        local_row = ttk.Frame(tab, style="TFrame")
        local_row.pack(fill=tk.X, padx=10, pady=(4, 8))

        ttk.Label(local_row, text="Modelo:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=self.config.get("local_model"))
        model_cb = ttk.Combobox(local_row, textvariable=self.model_var, state="readonly",
                                values=["tiny", "base", "small", "medium", "large-v3"], width=10)
        model_cb.pack(side=tk.LEFT, padx=(6, 12))
        model_cb.bind("<<ComboboxSelected>>",
                      lambda *_: self._on_change_local_model(self.model_var.get()))

        ttk.Label(local_row, text="Device:").pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value=self.config.get("local_device"))
        device_cb = ttk.Combobox(local_row, textvariable=self.device_var, state="readonly",
                                 values=["auto", "cpu", "cuda"], width=8)
        device_cb.pack(side=tk.LEFT, padx=(6, 12))
        device_cb.bind("<<ComboboxSelected>>",
                       lambda *_: self._on_change_local_device(self.device_var.get()))

        ttk.Button(local_row, text="Pre-cargar", command=self._on_warm_up_local
                   ).pack(side=tk.LEFT)
        ttk.Label(tab, text="La 1ra vez descarga el modelo (~50 MB tiny, ~3 GB large-v3).",
                  style="Subtitle.TLabel").pack(anchor="w", padx=10)

    def _build_tab_settings(self) -> None:
        tab = ttk.Frame(self.notebook, style="TFrame")
        self.notebook.add(tab, text="  Configuración  ")

        ttk.Label(tab, text="Groq API Key", style="Subtitle.TLabel").pack(anchor="w", padx=10, pady=(12, 4))
        key_row = ttk.Frame(tab, style="TFrame")
        key_row.pack(fill=tk.X, padx=10)
        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(key_row, textvariable=self.key_var, show="•")
        self.key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(key_row, text="Guardar",
                   command=lambda: self._on_change_groq_key(self.key_var.get() or None)
                   ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(key_row, text="Borrar",
                   command=lambda: (self.key_var.set(""),
                                    self._on_change_groq_key(None))
                   ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(tab, text="Se guarda con keyring (DPAPI). Nunca en texto plano.",
                  style="Subtitle.TLabel").pack(anchor="w", padx=10, pady=(2, 8))

        ttk.Separator(tab).pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(tab, text="Atajo de teclado", style="Subtitle.TLabel").pack(anchor="w", padx=10)
        hk_row = ttk.Frame(tab, style="TFrame")
        hk_row.pack(fill=tk.X, padx=10, pady=(4, 8))
        self.hotkey_var = tk.StringVar(value=self.config.get("hotkey"))
        ttk.Entry(hk_row, textvariable=self.hotkey_var, width=24).pack(side=tk.LEFT)
        ttk.Button(hk_row, text="Aplicar", command=self._apply_hotkey
                   ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(tab, text="Ejemplos: ctrl+alt+n  ·  ctrl+shift+space  ·  f9",
                  style="Subtitle.TLabel").pack(anchor="w", padx=10)

        ttk.Separator(tab).pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(tab, text="Backend ffmpeg (último recurso, para entornos con AV/EDR)",
                  style="Subtitle.TLabel").pack(anchor="w", padx=10)
        ff_row = ttk.Frame(tab, style="TFrame")
        ff_row.pack(fill=tk.X, padx=10, pady=(4, 8))
        self.ff_device_var = tk.StringVar(value=self.config.get("ffmpeg_device") or "")
        self.ff_device_combo = ttk.Combobox(ff_row, textvariable=self.ff_device_var,
                                            state="readonly", width=44)
        self.ff_device_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ff_device_combo.bind("<<ComboboxSelected>>",
                                  lambda *_: self._on_change_ffmpeg_device(self.ff_device_var.get()))
        ttk.Button(ff_row, text="↻", width=3, command=self.refresh_ffmpeg_devices
                   ).pack(side=tk.LEFT, padx=(6, 0))
        self.refresh_ffmpeg_devices()

        ttk.Separator(tab).pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(tab, text="Comportamiento", style="Subtitle.TLabel").pack(anchor="w", padx=10)
        self.var_top = tk.BooleanVar(value=bool(self.config.get("always_on_top")))
        self.var_paste = tk.BooleanVar(value=bool(self.config.get("auto_paste")))
        self.var_trim = tk.BooleanVar(value=bool(self.config.get("trim_silence")))
        for label, var, key in (
            ("Siempre encima",            self.var_top,     "always_on_top"),
            ("Auto-pegar al terminar",    self.var_paste,   "auto_paste"),
            ("Recortar silencios",        self.var_trim,    "trim_silence"),
        ):
            ttk.Checkbutton(tab, text=label, variable=var,
                            command=lambda k=key, v=var: self._toggle_setting(k, v)
                            ).pack(anchor="w", padx=14, pady=2)

    def _build_tab_log(self) -> None:
        # el log ahora vive en una ventana flotante (LogWindow)
        return

    # -------------------------------------------------------------- helpers
    def _draw_dot(self, color: str) -> None:
        self.status_dot.delete("all")
        self.status_dot.create_oval(2, 2, 12, 12, fill=color, outline="")

    def _toggle_setting(self, key: str, var: tk.BooleanVar) -> None:
        value = bool(var.get())
        self._on_change_setting(key, value)
        if key == "always_on_top" and not self.config.get("compact_mode"):
            self.root.attributes("-topmost", value)

    def _apply_hotkey(self) -> None:
        ok, msg = self._on_change_hotkey(self.hotkey_var.get().strip().lower())
        self.log(msg)
        if ok:
            self.hotkey_hint.config(text=f"Atajo: {self.hotkey_var.get().upper()}")

    def _on_mic_selected_radio(self) -> None:
        idx = int(self.mic_var.get())
        self._on_change_mic(idx)
        # marcar visualmente la fila seleccionada
        for w in self._mic_widgets:
            sel = (w["index"] == idx)
            w["name_label"].config(foreground=PALETTE["fg"] if sel else PALETTE["fg_dim"])

    def _toggle_compact(self) -> None:
        self._apply_compact(not bool(self.config.get("compact_mode", False)))

    def _apply_compact(self, compact: bool) -> None:
        self.config.set("compact_mode", compact)
        self.normal_frame.pack_forget()
        self.compact_frame.pack_forget()
        if compact:
            self.compact_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            self.root.geometry("220x110")
            self.root.attributes("-topmost", True)
        else:
            self.normal_frame.pack(fill=tk.BOTH, expand=True)
            self.root.geometry("520x640")
            self.root.attributes("-topmost", bool(self.config.get("always_on_top")))

    # ---------------------------------------------------------------- API
    # log() es inyectado por App() después de construir la LogWindow
    def log(self, message: str) -> None:  # placeholder; reemplazado por App
        pass

    def set_status(self, text: str, color: str = "fg_dim") -> None:
        def _apply():
            self.status_label.config(text=text)
            self.compact_status.config(text=text)
            self._draw_dot(PALETTE.get(color, PALETTE["fg_dim"]))
        self.root.after(0, _apply)

    def set_recording_button(self, recording: bool) -> None:
        def _apply():
            text = "■ Detener grabación" if recording else "● Iniciar grabación"
            short = "■ Detener" if recording else "● Grabar"
            style = "Danger.TButton" if recording else "Accent.TButton"
            self.record_btn.config(text=text, style=style)
            self.compact_record_btn.config(text=short, style=style)
        self.root.after(0, _apply)

    def set_service_status(self, text: str) -> None:
        self.root.after(0, lambda: self.service_status_label.config(text=text))

    def refresh_microphones(self) -> None:
        # detener meter previo
        self._stop_mic_meter()
        # limpiar filas
        for w in self._mic_widgets:
            try:
                w["row"].destroy()
            except Exception:
                pass
        self._mic_widgets.clear()

        try:
            devs = audio.list_input_devices()
        except Exception as e:
            self.log(f"No se pudo listar micrófonos: {e}")
            return

        configured = int(self.config.get("mic_index", -1))
        if not devs:
            ttk.Label(self.mic_list_frame, text="(sin micrófonos detectados)",
                      style="Subtitle.TLabel").pack(anchor="w", padx=4, pady=4)
            return

        # asegurar que haya una selección válida
        if configured == -1 or configured not in [d.index for d in devs]:
            for d in devs:
                if d.is_default:
                    self.mic_var.set(d.index)
                    break
            else:
                self.mic_var.set(devs[0].index)

        for d in devs:
            row = ttk.Frame(self.mic_list_frame, style="TFrame")
            row.pack(fill=tk.X, pady=2)
            radio = ttk.Radiobutton(row, value=d.index, variable=self.mic_var,
                                    command=self._on_mic_selected_radio)
            radio.pack(side=tk.LEFT)
            tag = " (default)" if d.is_default else ""
            display = (d.name[:38] + "…") if len(d.name) > 39 else d.name
            name_label = ttk.Label(row, text=display + tag, width=42)
            name_label.pack(side=tk.LEFT, padx=(4, 6))
            bar = tk.Canvas(row, width=140, height=10,
                            bg=PALETTE["bg_alt"], highlightthickness=0, bd=0)
            bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._mic_widgets.append({
                "index": d.index,
                "row": row,
                "name_label": name_label,
                "bar": bar,
            })

        # destacar la seleccionada
        selected = int(self.mic_var.get())
        for w in self._mic_widgets:
            w["name_label"].config(
                foreground=PALETTE["fg"] if w["index"] == selected else PALETTE["fg_dim"]
            )

        # arrancar meters: preferir sounddevice si está disponible (más estable en Windows 11)
        indices = [w["index"] for w in self._mic_widgets]
        if SD_AVAILABLE:
            self._mic_meter = SDMeterScanner(indices, log_fn=lambda m: self.log(m))
        else:
            self._mic_meter = MultiMicMeter(indices, log_fn=lambda m: self.log(m))
        try:
            self._mic_meter.start()
        except Exception as e:
            self.log(f"No se pudo iniciar VU: {e}")
            self._mic_meter = None
            return
        self._tick_mic_bars()
        # chequeo: si en 5s ningún mic dio señal y todos tienen error, avisar
        self.root.after(5000, self._check_mic_health)

    def _tick_mic_bars(self) -> None:
        if self._mic_meter is None or not self._mic_meter.running:
            return
        for w in self._mic_widgets:
            bar: tk.Canvas = w["bar"]
            level = self._mic_meter.get_level(w["index"])
            err = self._mic_meter.get_error(w["index"])
            bar.delete("all")
            width = max(1, bar.winfo_width())
            height = max(1, bar.winfo_height())
            if err:
                # rayita roja indicando error
                bar.create_rectangle(0, 0, width, height, fill=PALETTE["bg_alt"], outline="")
                bar.create_line(2, height // 2, width - 2, height // 2,
                                fill=PALETTE["err"], width=1)
                continue
            fill_w = int(width * min(1.0, max(0.0, level)))
            # fondo
            bar.create_rectangle(0, 0, width, height, fill=PALETTE["bg_alt"], outline="")
            # color según nivel
            if level > 0.85:
                color = PALETTE["err"]
            elif level > 0.5:
                color = PALETTE["warn"]
            elif level > 0.05:
                color = PALETTE["ok"]
            else:
                color = PALETTE["border"]
            if fill_w > 0:
                bar.create_rectangle(0, 0, fill_w, height, fill=color, outline="")
        self.root.after(60, self._tick_mic_bars)

    def _check_mic_health(self) -> None:
        if self._mic_meter is None:
            return
        all_failed = all(self._mic_meter.get_error(w["index"]) is not None
                         for w in self._mic_widgets)
        if all_failed and self._mic_widgets:
            self.log(
                "⚠ Todos los micrófonos rechazaron la apertura. "
                "Causa más probable en Windows: permisos de micrófono. "
                "Ve a Configuración → Privacidad y seguridad → Micrófono → "
                "activa 'Permitir que las aplicaciones de escritorio accedan al micrófono'. "
                "También cierra Teams/Zoom/Discord/OBS si están corriendo."
            )

    def _stop_mic_meter(self) -> None:
        if self._mic_meter is not None:
            try:
                self._mic_meter.stop()
            except Exception:
                pass
            self._mic_meter = None

    def stop_mic_meter(self) -> None:
        self._stop_mic_meter()

    def refresh_ffmpeg_devices(self) -> None:
        try:
            devs = self._list_ffmpeg_devices()
        except Exception as e:
            self.log(f"No se pudo listar devices de ffmpeg: {e}")
            return
        names = [d.name for d in devs]
        if not names:
            self.ff_device_combo["values"] = ["(ffmpeg no encontrado o sin devices)"]
            self.ff_device_combo.current(0)
            return
        self.ff_device_combo["values"] = names
        current = self.config.get("ffmpeg_device") or ""
        if current in names:
            self.ff_device_combo.current(names.index(current))
        else:
            self.ff_device_combo.current(0)

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self) -> None:
        self.root.withdraw()
