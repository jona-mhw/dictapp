"""Backend de captura usando ffmpeg como subprocess.

Razón: en endpoints corporativos con EDR/AV (Crowdstrike, SentinelOne,
Defender ATP) la API Win32 de audio queda bloqueada a procesos no
firmados como python.exe, pero ffmpeg suele estar permitido porque es
un binario firmado y conocido. Este backend evita por completo
PyAudio/sounddevice y delega la captura a `ffmpeg -f dshow`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable


def find_ffmpeg() -> str | None:
    """Busca ffmpeg en PATH o en el cwd."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    # carpeta del proyecto
    candidate = Path(__file__).resolve().parent.parent / "ffmpeg.exe"
    if candidate.is_file():
        return str(candidate)
    candidate = Path(__file__).resolve().parent.parent / "bin" / "ffmpeg.exe"
    if candidate.is_file():
        return str(candidate)
    return None


FFMPEG_AVAILABLE = find_ffmpeg() is not None


@dataclass
class FFDevice:
    name: str
    alt_name: str | None = None  # alternative name (más estable que el nombre legible)


def list_dshow_input_devices() -> list[FFDevice]:
    """Enumera devices de audio de DirectShow vía `ffmpeg -list_devices`."""
    exe = find_ffmpeg()
    if exe is None:
        return []
    try:
        proc = subprocess.run(
            [exe, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # ffmpeg devuelve la lista en stderr y exit code != 0 (es normal)
        out = proc.stderr or ""
    except Exception:
        return []

    # Parseo: ffmpeg lista bloques de "DirectShow video devices" y "DirectShow audio devices".
    # Cada device aparece como:  [dshow @ 0x...]  "Nombre del device"  (audio)
    # Inmediatamente abajo:      [dshow @ 0x...]    Alternative name "@device_..."
    devices: list[FFDevice] = []
    in_audio = False
    last_name: str | None = None
    for line in out.splitlines():
        if "DirectShow audio devices" in line:
            in_audio = True
            continue
        if "DirectShow video devices" in line:
            in_audio = False
            continue
        if not in_audio:
            continue
        m_name = re.search(r'"([^"]+)"\s*\((?:audio|none)\)?', line)
        if m_name and "(audio)" in line:
            last_name = m_name.group(1)
            devices.append(FFDevice(name=last_name))
            continue
        m_alt = re.search(r'Alternative name\s+"([^"]+)"', line)
        if m_alt and devices:
            devices[-1].alt_name = m_alt.group(1)
    return devices


class FFmpegRecorder:
    """Graba con ffmpeg → WAV temporal en disco. PCM s16le mono 16 kHz."""

    def __init__(self, device_name: str | None = None,
                 log_fn: Callable[[str], None] | None = None) -> None:
        self.device_name = device_name
        self.log_fn = log_fn or (lambda _msg: None)
        self._proc: subprocess.Popen | None = None
        self._wav_path: Path | None = None
        self._frames_buf: bytes = b""
        self._error: str | None = None
        self._sample_rate_used: int = 16000
        self._recording = False

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def sample_rate(self) -> int:
        return self._sample_rate_used

    @property
    def mic_index(self) -> int:
        return -1

    @mic_index.setter
    def mic_index(self, _value: int) -> None:
        # ffmpeg no usa índice; ignorado. Se usa device_name.
        pass

    def set_device_name(self, name: str | None) -> None:
        self.device_name = name

    def start(self) -> None:
        exe = find_ffmpeg()
        if exe is None:
            self._error = "ffmpeg no encontrado en PATH ni en la carpeta del proyecto."
            return
        if self._recording:
            return

        if not self.device_name:
            self._error = "No hay device DirectShow seleccionado para ffmpeg."
            return

        # WAV temporal de salida
        tmp = NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        self._wav_path = Path(tmp.name)
        self._error = None

        device_arg = f'audio={self.device_name}'
        cmd = [
            exe, "-hide_banner", "-loglevel", "warning",
            "-y",
            "-f", "dshow",
            "-i", device_arg,
            "-ac", "1",
            "-ar", "16000",
            "-acodec", "pcm_s16le",
            str(self._wav_path),
        ]
        self.log_fn(f"[ffmpeg] iniciando: {' '.join(cmd[:7])} … {self._wav_path.name}")

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            self._error = f"No se pudo iniciar ffmpeg: {e}"
            return

        # leer stderr en background para no bloquear y poder reportar errores
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._recording = True
        self._sample_rate_used = 16000

    def _drain_stderr(self) -> None:
        if self._proc is None or self._proc.stderr is None:
            return
        for line in iter(self._proc.stderr.readline, b""):
            try:
                txt = line.decode("utf-8", errors="replace").strip()
            except Exception:
                continue
            if txt:
                self.log_fn(f"[ffmpeg] {txt}")

    def stop(self) -> bytes:
        if not self._recording or self._proc is None:
            return self._read_wav_pcm()
        self._recording = False
        # señal q en stdin = ffmpeg termina graciosamente
        try:
            if self._proc.stdin is not None:
                self._proc.stdin.write(b"q")
                self._proc.stdin.flush()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                pass
        return self._read_wav_pcm()

    def _read_wav_pcm(self) -> bytes:
        if self._wav_path is None or not self._wav_path.exists():
            return b""
        try:
            with wave.open(str(self._wav_path), "rb") as wf:
                self._sample_rate_used = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
        except Exception as e:
            self._error = f"No se pudo leer WAV: {e}"
            pcm = b""
        finally:
            try:
                if self._wav_path is not None:
                    os.unlink(self._wav_path)
            except Exception:
                pass
            self._wav_path = None
        return pcm
