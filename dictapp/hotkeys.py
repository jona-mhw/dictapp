"""Wrapper de keyboard.add_hotkey con re-registro seguro."""
from __future__ import annotations

from typing import Callable

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except Exception:
    keyboard = None  # type: ignore
    KEYBOARD_AVAILABLE = False


class HotkeyManager:
    def __init__(self) -> None:
        self._handle = None
        self._combo: str | None = None

    @property
    def current(self) -> str | None:
        return self._combo

    def register(self, combo: str, callback: Callable[[], None]) -> tuple[bool, str]:
        if not KEYBOARD_AVAILABLE:
            return False, "keyboard no disponible"
        self.unregister()
        try:
            self._handle = keyboard.add_hotkey(combo, callback, suppress=False)
            self._combo = combo
            return True, f"Hotkey: {combo}"
        except Exception as e:
            self._handle = None
            self._combo = None
            return False, f"Error registrando hotkey: {e}"

    def unregister(self) -> None:
        if not KEYBOARD_AVAILABLE or self._handle is None:
            return
        try:
            keyboard.remove_hotkey(self._handle)
        except Exception:
            pass
        self._handle = None
        self._combo = None

    @staticmethod
    def send_paste() -> None:
        if KEYBOARD_AVAILABLE:
            keyboard.send("ctrl+v")
