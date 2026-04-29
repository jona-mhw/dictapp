"""Backend alternativo basado en sounddevice (mismo PortAudio, mejor binding).

Se usa como fallback cuando PyAudio falla con paUnanticipatedHostError (-9999),
algo común en Windows 11 con drivers Realtek/AMD modernos.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

try:
    import numpy as np
    import sounddevice as sd
    SD_AVAILABLE = True
except Exception:
    sd = None  # type: ignore
    np = None  # type: ignore
    SD_AVAILABLE = False


class SDRecorder:
    """Recorder con sounddevice. PCM int16 mono."""

    def __init__(self, mic_index: int = -1, log_fn: Callable[[str], None] | None = None) -> None:
        self.mic_index = mic_index
        self.log_fn = log_fn or (lambda _msg: None)
        self._frames: list[bytes] = []
        self._recording = False
        self._stream = None
        self._error: str | None = None
        self._sample_rate_used: int = 16000
        self._lock = threading.Lock()
        self._level: float = 0.0

    @property
    def level(self) -> float:
        return self._level

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def sample_rate(self) -> int:
        return self._sample_rate_used

    def _device_info(self, idx: int) -> dict:
        try:
            return dict(sd.query_devices(idx))
        except Exception:
            return {}

    def start(self) -> None:
        if not SD_AVAILABLE:
            self._error = "sounddevice no instalado"
            return
        if self._recording:
            return
        self._frames = []
        self._error = None

        idx = self.mic_index if (self.mic_index is not None and self.mic_index >= 0) else None
        info = self._device_info(idx) if idx is not None else {}
        native_rate = int(info.get("default_samplerate", 0) or 16000)
        native_ch = int(info.get("max_input_channels", 1) or 1)

        # combos: (rate, ch, dtype). float32 es lo que Windows shared-mode usa nativamente.
        rate_ch: list[tuple[int, int]] = []
        if native_ch and native_rate:
            rate_ch.append((native_rate, native_ch))
            if native_ch != 1:
                rate_ch.append((native_rate, 1))
        rate_ch.append((48000, 1))
        rate_ch.append((44100, 1))
        rate_ch.append((16000, 1))
        seen: set = set()
        rate_ch = [x for x in rate_ch if not (x in seen or seen.add(x))]

        attempts: list[tuple[str, int | None, int, int, str]] = []
        for rate, ch in rate_ch:
            for dtype in ("float32", "int16"):
                lab = f"idx={idx if idx is not None else 'DEFAULT'} @{rate}Hz {ch}ch {dtype}"
                attempts.append((lab, idx, rate, ch, dtype))
        # también probar default si idx existía
        if idx is not None:
            for rate, ch in rate_ch:
                for dtype in ("float32", "int16"):
                    lab = f"idx=DEFAULT @{rate}Hz {ch}ch {dtype}"
                    attempts.append((lab, None, rate, ch, dtype))

        last_err: Exception | None = None
        for label, dev, rate, ch, dtype in attempts:
            self.log_fn(f"[sd] Abriendo {label}")
            try:
                stream = sd.InputStream(
                    samplerate=rate,
                    channels=ch,
                    dtype=dtype,
                    device=dev,
                    blocksize=1024,
                    callback=self._make_callback(ch, dtype),
                )
                stream.start()
                self._stream = stream
                self._sample_rate_used = rate
                self._recording = True
                self.log_fn(f"[sd] Mic abierto OK con {label}.")
                return
            except Exception as e:
                last_err = e
                self.log_fn(f"[sd] Falló {label}: {e}")
                self._stream = None

        self._error = f"sounddevice no pudo abrir el mic. Último error: {last_err}"

    def _make_callback(self, channels: int, dtype: str):
        def cb(indata, _frames, _time_info, status):
            if status:
                self.log_fn(f"[sd] status: {status}")
            try:
                arr = indata
                if dtype == "float32":
                    if channels > 1:
                        arr = arr.mean(axis=1)
                    else:
                        arr = arr.reshape(-1)
                    arr = np.clip(arr, -1.0, 1.0)
                    arr_i16 = (arr * 32767.0).astype("int16")
                else:
                    if channels > 1:
                        arr_i16 = arr.mean(axis=1).astype("int16")
                    else:
                        arr_i16 = arr.reshape(-1).astype("int16")
                with self._lock:
                    self._frames.append(arr_i16.tobytes())
                # nivel
                try:
                    if arr_i16.size:
                        rms = float(np.sqrt(np.mean(arr_i16.astype("int32") ** 2)))
                        new_lvl = min(1.0, rms / 4000.0)
                        if new_lvl > self._level:
                            self._level = new_lvl
                        else:
                            self._level = self._level * 0.78 + new_lvl * 0.22
                except Exception:
                    pass
            except Exception as e:
                self.log_fn(f"[sd] error en callback: {e}")
        return cb

    def stop(self) -> bytes:
        self._recording = False
        self._level = 0.0
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        with self._lock:
            return b"".join(self._frames)


class SDLiveMeter:
    """Meter continuo de un solo mic. Mantiene un stream abierto y publica
    `level` (0..1) en tiempo real. Mucho más responsivo que el scanner
    round-robin porque no cierra/abre el stream cada 200 ms.
    """

    def __init__(self, mic_index: int | None, log_fn: Callable[[str], None] | None = None):
        self.mic_index = mic_index
        self.log_fn = log_fn or (lambda _msg: None)
        self._stream = None
        self._level = 0.0
        self._error: str | None = None
        self._lock = threading.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def level(self) -> float:
        return self._level

    @property
    def error(self) -> str | None:
        return self._error

    def start(self) -> None:
        if self._running or not SD_AVAILABLE:
            if not SD_AVAILABLE:
                self._error = "sounddevice no disponible"
            return
        self._error = None
        idx = self.mic_index if (self.mic_index is not None and self.mic_index >= 0) else None
        try:
            info = sd.query_devices(idx) if idx is not None else sd.query_devices(kind="input")
        except Exception as e:
            self._error = f"query_devices falló: {e}"
            return
        native_rate = int(info.get("default_samplerate", 0) or 16000)
        native_ch = int(info.get("max_input_channels", 1) or 1)

        # combos a intentar — empezamos por el modo nativo del device
        attempts: list[tuple[int, int, str]] = []
        for rate, ch in [(native_rate, native_ch), (native_rate, 1), (48000, 1), (16000, 1)]:
            for dtype in ("float32", "int16"):
                attempts.append((rate, ch, dtype))
        seen: set = set()
        attempts = [a for a in attempts if not (a in seen or seen.add(a))]

        last_err: Exception | None = None
        for rate, ch, dtype in attempts:
            try:
                stream = sd.InputStream(
                    samplerate=rate,
                    channels=ch,
                    dtype=dtype,
                    device=idx,
                    blocksize=512,
                    callback=self._make_callback(ch, dtype),
                )
                stream.start()
                self._stream = stream
                self._running = True
                return
            except Exception as e:
                last_err = e
                continue
        self._error = f"no se pudo abrir mic para VU: {last_err}"

    def _make_callback(self, channels: int, dtype: str):
        def cb(indata, _frames, _time, status):
            if status:
                self.log_fn(f"[vu] status: {status}")
            try:
                arr = indata
                if dtype == "float32":
                    arr = arr.mean(axis=1) if channels > 1 else arr.reshape(-1)
                    rms = float(np.sqrt(np.mean(arr * arr))) if arr.size else 0.0
                    level = min(1.0, rms * 6.0)
                else:
                    arr = arr.mean(axis=1).astype("int16") if channels > 1 else arr.reshape(-1).astype("int16")
                    rms = float(np.sqrt(np.mean(arr.astype("int32") ** 2))) if arr.size else 0.0
                    level = min(1.0, rms / 4000.0)
                # decaimiento suave: nuevo valor empuja hacia arriba rápido pero baja despacio
                with self._lock:
                    if level > self._level:
                        self._level = level
                    else:
                        self._level = self._level * 0.82 + level * 0.18
            except Exception as e:
                self.log_fn(f"[vu] callback err: {e}")
        return cb

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


