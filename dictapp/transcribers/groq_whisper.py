from __future__ import annotations

import time
from pathlib import Path

from .base import Transcriber, TranscriptionResult, TranscriptionError

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    Groq = None  # type: ignore
    GROQ_AVAILABLE = False


class GroqWhisperTranscriber(Transcriber):
    name = "Whisper (Groq)"

    def __init__(self, api_key: str | None, model: str = "whisper-large-v3") -> None:
        self.api_key = api_key
        self.model = model
        self._client = None
        if GROQ_AVAILABLE and api_key:
            try:
                self._client = Groq(api_key=api_key)
            except Exception:
                self._client = None

    def is_ready(self) -> tuple[bool, str]:
        if not GROQ_AVAILABLE:
            return False, "groq SDK no instalado"
        if not self.api_key:
            return False, "Falta API key de Groq"
        if self._client is None:
            return False, "Cliente Groq no inicializado"
        return True, "Listo"

    def transcribe(self, wav_path: Path, language: str = "es") -> TranscriptionResult:
        ok, msg = self.is_ready()
        if not ok:
            raise TranscriptionError(msg)
        t0 = time.perf_counter()
        try:
            with open(wav_path, "rb") as f:
                resp = self._client.audio.transcriptions.create(  # type: ignore[union-attr]
                    file=f,
                    model=self.model,
                    response_format="json",
                    language=language,
                )
        except Exception as e:
            raise TranscriptionError(f"Groq: {e}") from e

        text = getattr(resp, "text", None)
        if text is None and isinstance(resp, dict):
            text = resp.get("text")
        if not text:
            raise TranscriptionError("Groq: respuesta sin texto")
        return TranscriptionResult(text=text.strip(), backend=self.name, seconds=time.perf_counter() - t0)
