"""VU scanner secuencial: rota por todos los mics abriéndolos uno a la vez.

Razón: en Windows (MME/WASAPI) abrir N streams paralelos contra el mismo
sistema de audio satura PortAudio y todos fallan con 'Unanticipated host
error'. Con un scanner round-robin medimos RMS por turno (~200 ms cada uno)
sin nunca tener más de un stream abierto a la vez.
"""
from __future__ import annotations

import audioop
import threading
import time

import pyaudio

from . import audio as audio_mod

WINDOW_SEC = 0.18      # cuánto medimos cada mic antes de pasar al siguiente
DECAY = 0.55           # decaimiento del nivel cuando no es turno del mic


class MultiMicMeter:
    def __init__(self, indices: list[int], sample_rate: int = 16000, chunk: int = 512,
                 log_fn=None):
        self.indices = list(indices)
        self.sample_rate = sample_rate
        self.chunk = chunk
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
        if self._running or not self.indices:
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

    # --------------------------------------------------------------- loop
    def _loop(self) -> None:
        while self._running:
            for idx in self.indices:
                if not self._running:
                    return
                peak = self._sample_one(idx)
                # decaer el resto un poco para que la barra del que no medimos no se quede congelada
                for other in self.indices:
                    if other != idx:
                        self._levels[other] = self._levels[other] * DECAY
                if peak is not None:
                    self._levels[idx] = peak
                # pequeña pausa para liberar el host antes del siguiente
                time.sleep(0.02)

    def _sample_one(self, idx: int) -> float | None:
        pa = pyaudio.PyAudio()
        stream = None
        peak = 0.0
        try:
            info = pa.get_device_info_by_index(idx)
            native_rate = int(info.get("defaultSampleRate", 0)) or 44100
            native_ch = int(info.get("maxInputChannels", 1)) or 1
        except Exception:
            native_rate = 44100
            native_ch = 1

        # orden de intentos: nativo (lo que el host espera en shared-mode) -> mono nativo -> 16kHz
        attempts = [
            (native_rate, native_ch),
            (native_rate, 1),
            (self.sample_rate, 1),
        ]
        # dedupe preservando orden
        seen = set()
        attempts = [(r, c) for (r, c) in attempts if not ((r, c) in seen or seen.add((r, c)))]

        last_err: Exception | None = None
        used_channels = 1
        for rate, ch in attempts:
            try:
                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=ch,
                    rate=rate,
                    input=True,
                    frames_per_buffer=self.chunk,
                    input_device_index=idx,
                )
                used_channels = ch
                break
            except Exception as e:
                last_err = e
                stream = None
                continue

        if stream is None:
            err_text = f"errno={getattr(last_err, 'errno', None)} {last_err}"
            self._errors[idx] = err_text
            if idx not in self._reported:
                self._reported.add(idx)
                self.log_fn(f"VU mic#{idx}: no se pudo abrir ({err_text})")
            try:
                pa.terminate()
            except Exception:
                pass
            return None

        try:
            t_end = time.monotonic() + WINDOW_SEC
            while time.monotonic() < t_end and self._running:
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                except Exception as e:
                    self._errors[idx] = str(e)
                    return None
                if used_channels > 1:
                    try:
                        data = audioop.tomono(data, 2, 0.5, 0.5)
                    except Exception:
                        pass
                rms = audioop.rms(data, 2)
                level = min(1.0, rms / 6000.0)
                if level > peak:
                    peak = level
            self._errors.pop(idx, None)
            return peak
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            try:
                pa.terminate()
            except Exception:
                pass


def list_input_indices() -> list[audio_mod.MicDevice]:
    return audio_mod.list_input_devices()
