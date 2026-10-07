"""Selects an :class:`ImageGenerationProvider` implementation by configuration.
Defaults to :class:`NotConfiguredImageGenerationProvider` whenever a real
backend isn't fully configured, so callers always get the exact
"Image generation provider is not configured." message rather than a crash.
"""
from __future__ import annotations
from app.config.settings import Settings
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.not_configured import NotConfiguredImageGenerationProvider
class ImageGenerationProviderFactory:
    @staticmethod
    def create(settings: Settings) -> ImageGenerationProvider:
        name = (settings.image_provider or "none").strip().lower()
        if name == "openai" and settings.openai_api_key:
            from app.image_generation.openai_provider import OpenAIImageGenerationProvider
            return OpenAIImageGenerationProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_image_model,
                timeout_seconds=settings.request_timeout_seconds,
            )
        return NotConfiguredImageGenerationProvider()
