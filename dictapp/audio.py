"""Captura de audio desde micrófono."""
from __future__ import annotations

import threading
import wave
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable

import pyaudio

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
CHUNK = 1024
FORMAT = pyaudio.paInt16


@dataclass
class MicDevice:
    index: int
    name: str
    is_default: bool
    host_api: int = 0
    host_api_name: str = ""
    max_input_channels: int = 1
    default_sample_rate: int = 0


def list_input_devices() -> list[MicDevice]:
    p = pyaudio.PyAudio()
    devices: list[MicDevice] = []
    try:
        try:
            default_index = p.get_default_input_device_info().get("index", -1)
        except Exception:
            default_index = -1
        host_api_names: dict[int, str] = {}
        for h in range(p.get_host_api_count()):
            try:
                hinfo = p.get_host_api_info_by_index(h)
                host_api_names[int(hinfo.get("index", h))] = str(hinfo.get("name", f"HostApi{h}"))
            except Exception:
                pass
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if int(info.get("maxInputChannels", 0)) > 0:
                host_api = int(info.get("hostApi", 0))
                devices.append(
                    MicDevice(
                        index=i,
                        name=str(info.get("name", f"Mic {i}")),
                        is_default=(i == default_index),
                        host_api=host_api,
                        host_api_name=host_api_names.get(host_api, ""),
                        max_input_channels=int(info.get("maxInputChannels", 1)),
                        default_sample_rate=int(info.get("defaultSampleRate", 0)),
                    )
                )
    finally:
        p.terminate()
    return devices


def host_apis_summary() -> str:
    """Devuelve un string con info de host APIs y default device, para diagnóstico."""
    p = pyaudio.PyAudio()
    out: list[str] = []
    try:
        try:
            d = p.get_default_input_device_info()
            out.append(
                f"default input: idx={d.get('index')} name={d.get('name')!r} "
                f"hostApi={d.get('hostApi')} rate={d.get('defaultSampleRate')}"
            )
        except Exception as e:
            out.append(f"default input: ERROR {e}")
        for h in range(p.get_host_api_count()):
            try:
                hinfo = p.get_host_api_info_by_index(h)
                out.append(
                    f"hostApi[{h}]={hinfo.get('name')!r} default_input_idx={hinfo.get('defaultInputDevice')}"
                )
            except Exception:
                pass
    finally:
        p.terminate()
    return " · ".join(out)


def get_default_mic_name() -> str:
    p = pyaudio.PyAudio()
    try:
        info = p.get_default_input_device_info()
        return str(info.get("name", "Desconocido"))
    except Exception:
        return "Desconocido"
    finally:
        p.terminate()


# Prioridad de host API en Windows: WASAPI es lo que usan las apps modernas en
# shared mode; MME es el legacy de fallback. DirectSound y WDM-KS los
# descartamos del UI porque casi siempre son duplicados ruidosos.
_HOST_API_PRIORITY = {
    "Windows WASAPI": 0,
    "MME": 1,
}


def list_curated_input_devices() -> list[MicDevice]:
    """Devuelve un mic por dispositivo físico, sin duplicados de host API.

    Estrategia: preferir WASAPI; si no hay, caer a MME. Dedup por nombre.
    El que queda marcado como default es el que Windows reporta como default
    del sistema (lo mismo que toma cualquier app por defecto).
    """
    raw = list_input_devices()
    if not raw:
        return []
    for preferred in ("Windows WASAPI", "MME"):
        subset = [d for d in raw if d.host_api_name == preferred]
        if subset:
            seen: set[str] = set()
            uniq: list[MicDevice] = []
            for d in subset:
                if d.name in seen:
                    continue
                seen.add(d.name)
                uniq.append(d)
            default_name = get_default_mic_name()
            for d in uniq:
                d.is_default = (d.name == default_name)
            if not any(d.is_default for d in uniq):
                uniq[0].is_default = True
            uniq.sort(key=lambda x: (not x.is_default, x.name.lower()))
            return uniq
    # último recurso: lo que haya, dedup por nombre
    seen2: set[str] = set()
    out: list[MicDevice] = []
    for d in raw:
        if d.name in seen2:
            continue
        seen2.add(d.name)
        out.append(d)
    return out


class AudioRecorder:
    """Grabador push-to-toggle. Acumula PCM en memoria hasta stop()."""

    def __init__(self, mic_index: int = -1, log_fn: "Callable[[str], None] | None" = None) -> None:
        self.mic_index = mic_index
        self.log_fn = log_fn or (lambda _msg: None)
        self._frames: list[bytes] = []
        self._recording = False
        self._thread: threading.Thread | None = None
        self._error: str | None = None
        self._sample_rate_used: int = SAMPLE_RATE
        self._level: float = 0.0

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
    def level(self) -> float:
        return self._level

    def start(self) -> None:
        if self._recording:
            return
        self._frames = []
        self._error = None
        self._recording = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> bytes:
        if not self._recording:
            return b"".join(self._frames)
        self._recording = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        return b"".join(self._frames)

    def _device_info(self, p: pyaudio.PyAudio, idx: int) -> dict:
        try:
            return dict(p.get_device_info_by_index(idx))
        except Exception:
            return {}

    def _try_open(self, p: pyaudio.PyAudio, idx: "int | None", rate: int, channels: int):
        kwargs = dict(
            format=FORMAT,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=CHUNK,
        )
        if idx is not None and idx >= 0:
            kwargs["input_device_index"] = idx
        return p.open(**kwargs)

    def _describe_error(self, e: Exception) -> str:
        errno = getattr(e, "errno", None)
        text = str(e)
        suffix = ""
        if errno == -9999 or "9999" in text:
            suffix = " [paUnanticipatedHostError: el host de Windows rechazó la apertura — rate, formato o exclusivo]"
        elif errno == -9997 or "9997" in text:
            suffix = " [paInvalidSampleRate]"
        elif errno == -9998 or "9998" in text:
            suffix = " [paInvalidChannelCount]"
        elif errno == -9996 or "9996" in text:
            suffix = " [paInvalidDevice]"
        return f"errno={errno} msg={text}{suffix}"

    def _loop(self) -> None:
        p = pyaudio.PyAudio()
        stream = None
        captured_channels = CHANNELS
        try:
            # info del device elegido (si hay)
            info = self._device_info(p, self.mic_index) if self.mic_index is not None and self.mic_index >= 0 else {}
            native_rate = int(info.get("defaultSampleRate", 0)) or 44100
            native_ch = int(info.get("maxInputChannels", 1)) or 1

            attempts: list[tuple[str, int | None, int, int]] = []
            # 1) Modo nativo del device (lo que WASAPI/MME esperan en shared mode)
            if self.mic_index is not None and self.mic_index >= 0:
                attempts.append((f"device idx={self.mic_index} NATIVO @{native_rate}Hz {native_ch}ch",
                                 self.mic_index, native_rate, native_ch))
                # 2) device elegido @ native rate, 1 canal (forzando mono)
                if native_ch != 1:
                    attempts.append((f"device idx={self.mic_index} @{native_rate}Hz 1ch",
                                     self.mic_index, native_rate, 1))
                # 3) device elegido @ 16kHz, 1 canal
                attempts.append((f"device idx={self.mic_index} @16kHz 1ch",
                                 self.mic_index, SAMPLE_RATE, 1))
            # 4) default del sistema en su modo nativo
            try:
                d = p.get_default_input_device_info()
                d_rate = int(d.get("defaultSampleRate", 0)) or 44100
                d_ch = int(d.get("maxInputChannels", 1)) or 1
                attempts.append((f"DEFAULT NATIVO @{d_rate}Hz {d_ch}ch", None, d_rate, d_ch))
                if d_ch != 1:
                    attempts.append((f"DEFAULT @{d_rate}Hz 1ch", None, d_rate, 1))
            except Exception:
                pass
            # 5) último recurso
            attempts.append(("DEFAULT @44100Hz 1ch", None, 44100, 1))
            attempts.append(("DEFAULT @16kHz 1ch", None, SAMPLE_RATE, 1))

            last_err = None
            for label, idx, rate, channels in attempts:
                ainfo = self._device_info(p, idx) if idx is not None else {}
                self.log_fn(
                    f"Abriendo mic [{label}] hostApi={ainfo.get('hostApi')} "
                    f"name={ainfo.get('name')!r}"
                )
                try:
                    stream = self._try_open(p, idx, rate, channels)
                    self._sample_rate_used = rate
                    captured_channels = channels
                    self.log_fn(f"Mic abierto OK con [{label}].")
                    break
                except Exception as e:
                    last_err = e
                    self.log_fn(f"Falló [{label}]: {self._describe_error(e)}")
                    stream = None

            if stream is None:
                hint = ""
                if last_err is not None and getattr(last_err, "errno", None) == -9999:
                    hint = (
                        "  ► Verifica: Configuración de Windows → Privacidad → Micrófono → "
                        "'Permitir que las apps de escritorio accedan al micrófono' debe estar ENCENDIDO. "
                        "También cierra otras apps que puedan tener el mic en exclusivo (Teams, Zoom, OBS, Discord)."
                    )
                self._error = (
                    f"No se pudo abrir ningún micrófono. Último error: "
                    f"{self._describe_error(last_err) if last_err else 'desconocido'}.{hint}"
                )
                return

            import audioop
            while self._recording:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    if captured_channels > 1:
                        try:
                            data = audioop.tomono(data, SAMPLE_WIDTH, 0.5, 0.5)
                        except Exception:
                            pass
                    self._frames.append(data)
                    try:
                        rms = audioop.rms(data, SAMPLE_WIDTH)
                        new_lvl = min(1.0, rms / 4000.0)
                        # subir rápido, bajar suave
                        if new_lvl > self._level:
                            self._level = new_lvl
                        else:
                            self._level = self._level * 0.78 + new_lvl * 0.22
                    except Exception:
                        pass
                except Exception as e:
                    self._error = f"Error durante grabación: {self._describe_error(e)}"
                    break
            self._level = 0.0
        except Exception as e:
            self._error = f"No se pudo abrir el micrófono: {self._describe_error(e)}"
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            p.terminate()


def trim_silence(pcm: bytes, threshold: int | None = None,
                 sample_width: int = SAMPLE_WIDTH,
                 sample_rate: int = SAMPLE_RATE) -> bytes:
    """Recorta silencios al inicio y al final basándose en amplitud relativa.

    Si `threshold` es None, calcula uno adaptativo según el pico de la grabación
    (15% del RMS máximo, con piso 120). Esto evita comerse audio en mics
    silenciosos donde un threshold fijo es demasiado alto.
    """
    if not pcm or sample_width != 2:
        return pcm
    import audioop
    try:
        # ventana 50 ms al sample rate REAL
        win = int(sample_rate * 0.05) * sample_width
        if win <= 0 or win > len(pcm):
            return pcm
        # threshold adaptativo: 15% del pico, mínimo 120
        if threshold is None:
            peak = 0
            scan_pos = 0
            while scan_pos + win <= len(pcm):
                rms_v = audioop.rms(pcm[scan_pos:scan_pos + win], sample_width)
                if rms_v > peak:
                    peak = rms_v
                scan_pos += win
            threshold = max(120, int(peak * 0.15))
            # si el pico es realmente bajo, no recortes nada (mic silencioso)
            if peak < 200:
                return pcm
        start = 0
        end = len(pcm)
        while start + win <= end:
            if audioop.rms(pcm[start:start + win], sample_width) > threshold:
                break
            start += win
        while end - win > start:
            if audioop.rms(pcm[end - win:end], sample_width) > threshold:
                break
            end -= win
        # padding 200 ms a cada lado para no cortar consonantes
        pad = int(sample_rate * 0.2) * sample_width
        start = max(0, start - pad)
        end = min(len(pcm), end + pad)
        # safety: si quedaría < 25% del original, mejor devolver el original
        if (end - start) < len(pcm) * 0.25:
            return pcm
        return pcm[start:end] if end > start else pcm
    except Exception:
        return pcm


@contextmanager
def pcm_to_wav_temp(pcm: bytes, sample_rate: int = SAMPLE_RATE):
    """Escribe PCM crudo a un WAV temporal y lo elimina al salir."""
    tmp = NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    path = Path(tmp.name)
    try:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def duration_seconds(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> float:
    if not pcm:
        return 0.0
    return len(pcm) / (sample_rate * SAMPLE_WIDTH * CHANNELS)


# tipo de callback usado por el orquestador
LogFn = Callable[[str], None]
