"""``SpeechToTextProvider`` / ``TextToSpeechProvider`` interfaces.
Only the interfaces (and a default "not configured" implementation) are
provided in this part - concrete provider implementations (e.g. Whisper,
ElevenLabs, ...) are left as TODO until a voice service is configured, per
the Part 3 scope.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from app.voice.models import SynthesisResult, TranscriptionResult
class SpeechToTextProvider(ABC):
    """Abstract interface for converting audio into text."""
    name: str = "base"
    @abstractmethod
    async def transcribe(self, audio: bytes, mime_type: str, language: str | None = None) -> TranscriptionResult:
        """Transcribe ``audio`` (raw bytes) into text.
        Raises:
            app.models.errors.ProviderConfigurationError: If no real
                provider is configured.
            app.models.errors.ModelError: If transcription fails.
        """
    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
class TextToSpeechProvider(ABC):
    """Abstract interface for converting text into audio."""
    name: str = "base"
    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> SynthesisResult:
        """Synthesize speech audio for ``text``.
        Raises:
            app.models.errors.ProviderConfigurationError: If no real
                provider is configured.
            app.models.errors.ModelError: If synthesis fails.
        """
    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
