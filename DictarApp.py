"""Entry point de DictarApp v0.4.

Ejecuta:
    python DictarApp.py

Las dependencias están en requirements.txt.
"""
from __future__ import annotations

import sys
import subprocess
from importlib import util as importutil


REQUIRED = [
    ("pyaudio", "pyaudio"),
    ("pyperclip", "pyperclip"),
    ("groq", "groq"),
    ("pystray", "pystray"),
    ("PIL", "Pillow"),
    ("keyboard", "keyboard"),
    ("keyring", "keyring"),
]
OPTIONAL = [
    ("speech_recognition", "SpeechRecognition"),
    ("faster_whisper", "faster-whisper"),
]


def _missing(packages: list[tuple[str, str]]) -> list[str]:
    out = []
    for module, pip_name in packages:
        if importutil.find_spec(module) is None:
            out.append(pip_name)
    return out


def _check_dependencies() -> None:
    missing = _missing(REQUIRED)
    if not missing:
        return
    print("Faltan dependencias requeridas:", ", ".join(missing))
    try:
        print("Instalando con pip…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    except subprocess.CalledProcessError as e:
        print(f"\nError al instalar: {e}")
        print("Instala manualmente: pip install " + " ".join(missing))
        sys.exit(1)


def main() -> None:
    _check_dependencies()
    # importar después de asegurar deps
    from dictapp.app import App
    App().run()


if __name__ == "__main__":
    main()
