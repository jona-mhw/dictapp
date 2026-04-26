from __future__ import annotations

import time
from pathlib import Path

from .base import Transcriber, TranscriptionResult, TranscriptionError

try:
    import speech_recognition as sr
    GOOGLE_AVAILABLE = True
except Exception:
    sr = None  # type: ignore
    GOOGLE_AVAILABLE = False


class GoogleTranscriber(Transcriber):
    name = "Google"

    def is_ready(self) -> tuple[bool, str]:
        if not GOOGLE_AVAILABLE:
            return False, "SpeechRecognition no instalado"
        return True, "Listo (endpoint público)"

    def transcribe(self, wav_path: Path, language: str = "es") -> TranscriptionResult:
        if not GOOGLE_AVAILABLE:
            raise TranscriptionError("SpeechRecognition no instalado")
        recognizer = sr.Recognizer()
        t0 = time.perf_counter()
        try:
            with sr.AudioFile(str(wav_path)) as source:
                audio = recognizer.record(source)
            lang_map = {"es": "es-ES", "en": "en-US"}
            text = recognizer.recognize_google(audio, language=lang_map.get(language, language))
        except sr.UnknownValueError as e:
            raise TranscriptionError("Google: no se entendió el audio") from e
        except sr.RequestError as e:
            raise TranscriptionError(f"Google: {e}") from e
        except Exception as e:
            raise TranscriptionError(f"Google: {e}") from e
        return TranscriptionResult(text=text.strip(), backend=self.name, seconds=time.perf_counter() - t0)
