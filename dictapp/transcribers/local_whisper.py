"""Whisper local con faster-whisper."""
from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

from .base import Transcriber, TranscriptionResult, TranscriptionError

try:
    from faster_whisper import WhisperModel
    LOCAL_AVAILABLE = True
except Exception:
    WhisperModel = None  # type: ignore
    LOCAL_AVAILABLE = False


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _resolve_compute_type(compute_type: str, device: str) -> str:
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


class LocalWhisperTranscriber(Transcriber):
    name = "Whisper local"

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        log_fn=None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._loaded_with: tuple[str, str, str] | None = None
        self._lock = Lock()
        self._load_error: str | None = None
        self.log_fn = log_fn or (lambda _msg: None)

    def is_ready(self) -> tuple[bool, str]:
        if not LOCAL_AVAILABLE:
            return False, "faster-whisper no instalado"
        if self._load_error:
            return False, self._load_error
        return True, f"Modelo {self.model_size} ({self._effective_device()})"

    def _effective_device(self) -> str:
        return _resolve_device(self.device)

    def _ensure_loaded(self) -> None:
        if not LOCAL_AVAILABLE:
            raise TranscriptionError("faster-whisper no instalado")
        target = (self.model_size, self.device, self.compute_type)
        with self._lock:
            if self._model is not None and self._loaded_with == target:
                return
            try:
                device = _resolve_device(self.device)
                compute_type = _resolve_compute_type(self.compute_type, device)
                self.log_fn(f"[local-whisper] cargando modelo='{self.model_size}' device='{device}' compute='{compute_type}'…")
                t0 = time.perf_counter()
                self._model = WhisperModel(  # type: ignore[misc]
                    self.model_size,
                    device=device,
                    compute_type=compute_type,
                )
                self.log_fn(f"[local-whisper] modelo cargado en {time.perf_counter()-t0:.2f}s")
                self._loaded_with = target
                self._load_error = None
            except Exception as e:
                hint = ""
                msg = str(e)
                if "locate" in msg.lower() or "hugging" in msg.lower() or "connection" in msg.lower():
                    hint = " (revisa tu conexión: el modelo se descarga de HuggingFace en la 1ra carga)"
                elif "cuda" in msg.lower() or "cublas" in msg.lower() or "cudnn" in msg.lower():
                    hint = " (problema con CUDA: prueba device='cpu')"
                self._load_error = f"No se pudo cargar Whisper local: {e}{hint}"
                raise TranscriptionError(self._load_error) from e

    def warm_up(self) -> None:
        try:
            self._ensure_loaded()
        except TranscriptionError:
            pass

    def _run_inference(self, wav_path: Path, language: str) -> tuple[list, object, float]:
        assert self._model is not None
        t0 = time.perf_counter()
        segments, info = self._model.transcribe(
            str(wav_path),
            language=language,
            vad_filter=True,
        )
        seg_list = list(segments)  # forzar evaluación del generador
        return seg_list, info, time.perf_counter() - t0

    def transcribe(self, wav_path: Path, language: str = "es") -> TranscriptionResult:
        self._ensure_loaded()
        size = wav_path.stat().st_size if wav_path.exists() else -1
        self.log_fn(f"[local-whisper] transcribe wav='{wav_path}' size={size} bytes lang='{language}'")
        try:
            seg_list, info, elapsed = self._run_inference(wav_path, language)
        except RuntimeError as e:
            msg = str(e).lower()
            cuda_issue = ("cublas" in msg or "cudnn" in msg or "cuda" in msg)
            if cuda_issue and self._effective_device() == "cuda":
                self.log_fn(f"[local-whisper] CUDA falló ({e}); reintentando en CPU (int8)…")
                with self._lock:
                    self._model = None
                    self._loaded_with = None
                self.device = "cpu"
                self.compute_type = "int8"
                try:
                    self._ensure_loaded()
                    seg_list, info, elapsed = self._run_inference(wav_path, language)
                except Exception as e2:
                    self.log_fn(f"[local-whisper] fallback CPU también falló: {type(e2).__name__}: {e2}")
                    raise TranscriptionError(f"Whisper local (fallback CPU): {e2}") from e2
            else:
                self.log_fn(f"[local-whisper] EXC durante transcribe: {type(e).__name__}: {e}")
                raise TranscriptionError(f"Whisper local: {e}") from e
        except Exception as e:
            self.log_fn(f"[local-whisper] EXC durante transcribe: {type(e).__name__}: {e}")
            raise TranscriptionError(f"Whisper local: {e}") from e

        text = "".join(s.text for s in seg_list).strip()
        self.log_fn(
            f"[local-whisper] OK · segments={len(seg_list)} · "
            f"detected_lang={getattr(info, 'language', '?')} "
            f"prob={getattr(info, 'language_probability', 0):.2f} "
            f"audio_dur={getattr(info, 'duration', 0):.2f}s "
            f"elapsed={elapsed:.2f}s · device={self._effective_device()}"
        )
        if not text:
            self.log_fn("[local-whisper] sin texto reconocido (segments vacíos o solo whitespace)")
            raise TranscriptionError("Whisper local: sin texto reconocido")
        return TranscriptionResult(text=text, backend=self.name, seconds=elapsed)
