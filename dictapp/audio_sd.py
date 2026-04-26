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


def list_input_devices() -> list[dict]:
    if not SD_AVAILABLE:
        return []
    devs = []
    try:
        all_devs = sd.query_devices()
        try:
            default_in_idx = sd.default.device[0]
        except Exception:
            default_in_idx = -1
        host_apis = sd.query_hostapis()
        for i, d in enumerate(all_devs):
            if int(d.get("max_input_channels", 0)) > 0:
                ha = int(d.get("hostapi", 0))
                ha_name = host_apis[ha]["name"] if ha < len(host_apis) else ""
                devs.append({
                    "index": i,
                    "name": str(d.get("name", f"Mic {i}")),
                    "max_input_channels": int(d.get("max_input_channels", 1)),
                    "default_sample_rate": int(d.get("default_samplerate", 0) or 0),
                    "host_api": ha,
                    "host_api_name": ha_name,
                    "is_default": (i == default_in_idx),
                })
    except Exception:
        pass
    return devs


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
                    # mezclar a mono y convertir a int16 PCM
                    if channels > 1:
                        arr = arr.mean(axis=1)
                    else:
                        arr = arr.reshape(-1)
                    arr = np.clip(arr, -1.0, 1.0)
                    arr = (arr * 32767.0).astype("int16")
                else:
                    if channels > 1:
                        arr = arr.mean(axis=1).astype("int16")
                    else:
                        arr = arr.reshape(-1).astype("int16")
                with self._lock:
                    self._frames.append(arr.tobytes())
            except Exception as e:
                self.log_fn(f"[sd] error en callback: {e}")
        return cb

    def stop(self) -> bytes:
        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        with self._lock:
            return b"".join(self._frames)


class SDMeterScanner:
    """Scanner round-robin con sounddevice."""

    def __init__(self, indices: list[int], log_fn: Callable[[str], None] | None = None):
        self.indices = list(indices)
        self.log_fn = log_fn or (lambda _msg: None)
        self._levels: dict[int, float] = {i: 0.0 for i in self.indices}
        self._errors: dict[int, str] = {}
        self._reported: set[int] = set()
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running or not self.indices or not SD_AVAILABLE:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None

    def get_level(self, idx: int) -> float:
        return self._levels.get(idx, 0.0)

    def get_error(self, idx: int) -> str | None:
        return self._errors.get(idx)

    def _loop(self) -> None:
        while self._running:
            for idx in self.indices:
                if not self._running:
                    return
                peak = self._sample_one(idx)
                for other in self.indices:
                    if other != idx:
                        self._levels[other] = self._levels[other] * 0.55
                if peak is not None:
                    self._levels[idx] = peak
                time.sleep(0.02)

    def _sample_one(self, idx: int) -> float | None:
        try:
            info = sd.query_devices(idx)
            native_rate = int(info.get("default_samplerate", 0) or 44100)
            native_ch = int(info.get("max_input_channels", 1) or 1)
        except Exception:
            native_rate = 44100
            native_ch = 1

        rate_ch = [(native_rate, native_ch), (native_rate, 1), (48000, 1), (16000, 1)]
        seen: set = set()
        rate_ch = [x for x in rate_ch if not (x in seen or seen.add(x))]

        peak = 0.0
        last_err: Exception | None = None
        for rate, ch in rate_ch:
            for dtype in ("float32", "int16"):
                peak_box = {"v": 0.0}

                def cb(indata, _frames, _time, _status, dtype=dtype, ch=ch):
                    arr = indata
                    if dtype == "float32":
                        arr = arr.mean(axis=1) if ch > 1 else arr.reshape(-1)
                        rms = float(np.sqrt(np.mean(arr * arr))) if arr.size else 0.0
                        level = min(1.0, rms * 4.0)  # float32 va de -1..1
                    else:
                        arr = arr.mean(axis=1).astype("int16") if ch > 1 else arr.reshape(-1).astype("int16")
                        rms = float(np.sqrt(np.mean(arr.astype("int32") ** 2))) if arr.size else 0.0
                        level = min(1.0, rms / 6000.0)
                    if level > peak_box["v"]:
                        peak_box["v"] = level

                try:
                    stream = sd.InputStream(samplerate=rate, channels=ch, dtype=dtype,
                                            device=idx, blocksize=512, callback=cb)
                    stream.start()
                    t_end = time.monotonic() + 0.18
                    while time.monotonic() < t_end and self._running:
                        time.sleep(0.02)
                    stream.stop()
                    stream.close()
                    if peak_box["v"] > peak:
                        peak = peak_box["v"]
                    self._errors.pop(idx, None)
                    return peak
                except Exception as e:
                    last_err = e
                    continue

        err_text = f"{last_err}"
        self._errors[idx] = err_text
        if idx not in self._reported:
            self._reported.add(idx)
            self.log_fn(f"[sd] VU mic#{idx}: no se pudo abrir ({err_text})")
        return None
