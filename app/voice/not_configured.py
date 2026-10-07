"""Default voice providers used until a real speech service is configured.
TODO (future part): implement real ``SpeechToTextProvider`` / ``TextToSpeechProvider``
backends (e.g. Whisper, ElevenLabs) once a voice service is configured.
"""
from __future__ import annotations
from app.models.errors import ProviderConfigurationError
from app.voice.base import SpeechToTextProvider, TextToSpeechProvider
from app.voice.models import SynthesisResult, TranscriptionResult
STT_NOT_CONFIGURED_MESSAGE = "Speech-to-text provider is not configured."
TTS_NOT_CONFIGURED_MESSAGE = "Text-to-speech provider is not configured."
class NotConfiguredSpeechToTextProvider(SpeechToTextProvider):
    name = "none"
    async def transcribe(
        self, audio: bytes, mime_type: str, language: str | None = None
    ) -> TranscriptionResult:
        raise ProviderConfigurationError(STT_NOT_CONFIGURED_MESSAGE)
    async def health_check(self) -> bool:
        return False
class NotConfiguredTextToSpeechProvider(TextToSpeechProvider):
    name = "none"
    async def synthesize(self, text: str, voice: str | None = None) -> SynthesisResult:
        raise ProviderConfigurationError(TTS_NOT_CONFIGURED_MESSAGE)
    async def health_check(self) -> bool:
        return False
