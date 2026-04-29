"""Icono en bandeja del sistema."""
from __future__ import annotations

import threading
from typing import Callable

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except Exception:
    pystray = None  # type: ignore
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    TRAY_AVAILABLE = False

from .version import APP_NAME

_COLORS = {
    "idle":        (124, 92, 255),
    "recording":   (255, 107, 107),
    "transcribing":(245, 185, 66),
    "ok":          (61, 220, 132),
    "error":       (180, 60, 60),
}


def _make_image(state: str):
    color = _COLORS.get(state, _COLORS["idle"])
    img = Image.new("RGB", (64, 64), (30, 31, 36))
    d = ImageDraw.Draw(img)
    d.ellipse((10, 10, 54, 54), fill=color)
    return img


def _make_level_image(level: float):
    """Icono mientras se graba: anillo rojo + relleno proporcional al nivel."""
    level = max(0.0, min(1.0, level))
    img = Image.new("RGB", (64, 64), (30, 31, 36))
    d = ImageDraw.Draw(img)
    # anillo exterior rojo (estado grabando)
    d.ellipse((6, 6, 58, 58), outline=_COLORS["recording"], width=3)
    # disco interno cuyo radio crece con el nivel
    base_r = 6
    extra = int(level * 18)
    r = base_r + extra
    cx, cy = 32, 32
    # color: pasa de naranja → rojo conforme sube
    if level > 0.7:
        fill = (255, 80, 80)
    elif level > 0.3:
        fill = (245, 165, 85)
    else:
        fill = (200, 80, 80)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    return img


class TrayIcon:
    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_toggle: Callable[[], None],
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_toggle = on_toggle
        self.icon = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not TRAY_AVAILABLE:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar", lambda *_: self._on_show()),
            pystray.MenuItem("Iniciar/detener grabación", lambda *_: self._on_toggle()),
            pystray.MenuItem("Salir", lambda *_: self._on_quit()),
        )
        self.icon = pystray.Icon(APP_NAME, _make_image("idle"), APP_NAME, menu)
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def set_state(self, state: str) -> None:
        if not TRAY_AVAILABLE or self.icon is None:
            return
        try:
            self.icon.icon = _make_image(state)
        except Exception:
            pass

    def set_level(self, level: float) -> None:
        """Actualiza el icono con un disco proporcional al nivel (estado grabando)."""
        if not TRAY_AVAILABLE or self.icon is None:
            return
        try:
            self.icon.icon = _make_level_image(level)
        except Exception:
            pass

    def stop(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
