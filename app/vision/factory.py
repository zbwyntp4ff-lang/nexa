"""Selects a :class:`app.vision.base.VisionProvider` implementation by configuration."""
from __future__ import annotations
from app.config.settings import Settings
from app.models.errors import ProviderConfigurationError
from app.vision.base import VisionProvider
from app.vision.mock import MockVisionProvider
SUPPORTED_VISION_PROVIDERS: tuple[str, ...] = ("mock", "openai")
class VisionProviderFactory:
    @staticmethod
    def create(settings: Settings) -> VisionProvider:
        name = (settings.vision_provider or "mock").strip().lower()
        if name == "mock":
            return MockVisionProvider()
        if name == "openai":
            from app.vision.openai_provider import OpenAIVisionProvider
            return OpenAIVisionProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_vision_model,
                timeout_seconds=settings.request_timeout_seconds,
            )
        raise ProviderConfigurationError(
            f"Unknown vision provider '{name}'. Available: {', '.join(SUPPORTED_VISION_PROVIDERS)}."
        )
