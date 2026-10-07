"""Factories for the voice providers.
Both default to their "not configured" implementation - no real
``STT_PROVIDER``/``TTS_PROVIDER`` backend is implemented yet (TODO, per the
Part 3 scope: "Пока можно оставить provider implementations как TODO").
"""
from __future__ import annotations
from app.config.settings import Settings
from app.voice.base import SpeechToTextProvider, TextToSpeechProvider
from app.voice.not_configured import NotConfiguredSpeechToTextProvider, NotConfiguredTextToSpeechProvider
class SpeechToTextProviderFactory:
    @staticmethod
    def create(settings: Settings) -> SpeechToTextProvider:
        # TODO: once a real STT backend is added, branch on settings.stt_provider here.
        return NotConfiguredSpeechToTextProvider()
class TextToSpeechProviderFactory:
    @staticmethod
    def create(settings: Settings) -> TextToSpeechProvider:
        # TODO: once a real TTS backend is added, branch on settings.tts_provider here.
        return NotConfiguredTextToSpeechProvider()
