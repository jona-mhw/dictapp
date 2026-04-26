"""Configuración persistente.

- Preferencias no sensibles -> settings.json en %APPDATA%/DictarApp/.
- Secretos (API keys) -> keyring (DPAPI en Windows).
- Migración automática desde el viejo HKCU\\SOFTWARE\\TranscriptionApp\\GroqApiKey.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import keyring
    KEYRING_OK = True
except Exception:
    KEYRING_OK = False

try:
    import winreg
except ImportError:
    winreg = None

from .version import APP_NAME

KEYRING_SERVICE = "DictarApp"
KEYRING_GROQ_USER = "groq_api_key"

DEFAULT_SETTINGS: dict[str, Any] = {
    "service": "Whisper (Groq)",                 # "Whisper (Groq)" | "Google" | "Whisper local"
    "hotkey": "ctrl+alt+n",
    "always_on_top": False,
    "compact_mode": False,
    "auto_paste": True,
    "trim_silence": True,
    "mic_index": -1,                              # -1 = default
    "ffmpeg_device": "",                          # nombre DirectShow (audio=...) para backend ffmpeg
    "local_model": "base",                        # tiny|base|small|medium|large-v3
    "local_device": "auto",                       # auto|cpu|cuda
    "local_compute_type": "auto",                 # auto|int8|int8_float16|float16|float32
    "language": "es",
    "last_seen_version": "",                      # para popup What's New
}


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def settings_path() -> Path:
    return _appdata_dir() / "settings.json"


class Config:
    def __init__(self) -> None:
        self.path = settings_path()
        self.data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k in DEFAULT_SETTINGS:
                            self.data[k] = v
            except (OSError, json.JSONDecodeError):
                pass

    def save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    # ----- secretos -----
    def get_groq_key(self) -> str | None:
        if KEYRING_OK:
            try:
                value = keyring.get_password(KEYRING_SERVICE, KEYRING_GROQ_USER)
                if value:
                    return value
            except Exception:
                pass
        # fallback / migración: registro viejo
        legacy = self._read_legacy_registry_key()
        if legacy and KEYRING_OK:
            try:
                keyring.set_password(KEYRING_SERVICE, KEYRING_GROQ_USER, legacy)
                self._delete_legacy_registry_key()
            except Exception:
                pass
        return legacy

    def set_groq_key(self, key: str | None) -> None:
        if not KEYRING_OK:
            raise RuntimeError("keyring no disponible. Instala 'keyring'.")
        if key:
            keyring.set_password(KEYRING_SERVICE, KEYRING_GROQ_USER, key)
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_GROQ_USER)
            except Exception:
                pass

    @staticmethod
    def _read_legacy_registry_key() -> str | None:
        if winreg is None:
            return None
        try:
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\TranscriptionApp",
                0,
                winreg.KEY_READ,
            )
            value, _ = winreg.QueryValueEx(k, "GroqApiKey")
            winreg.CloseKey(k)
            return value or None
        except OSError:
            return None

    @staticmethod
    def _delete_legacy_registry_key() -> None:
        if winreg is None:
            return
        try:
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\TranscriptionApp",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.DeleteValue(k, "GroqApiKey")
            winreg.CloseKey(k)
        except OSError:
            pass
