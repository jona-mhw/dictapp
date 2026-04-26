from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class TranscriptionError(Exception):
    pass


@dataclass
class TranscriptionResult:
    text: str
    backend: str
    seconds: float = 0.0


class Transcriber(ABC):
    name: str = "base"

    @abstractmethod
    def is_ready(self) -> tuple[bool, str]:
        """Devuelve (listo, mensaje_de_estado)."""

    @abstractmethod
    def transcribe(self, wav_path: Path, language: str = "es") -> TranscriptionResult:
        ...
