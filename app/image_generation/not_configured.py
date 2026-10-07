"""The default image generation provider: no image model is configured.
Deliberately does **not** fabricate a fake image - it reports clearly that
image generation is unavailable so the caller can handle it explicitly.
"""
from __future__ import annotations
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.models import ImageGenerationResult
from app.models.errors import ProviderConfigurationError
NOT_CONFIGURED_MESSAGE = "Image generation provider is not configured."
class NotConfiguredImageGenerationProvider(ImageGenerationProvider):
    name = "none"
    async def generate(self, prompt: str, **kwargs) -> ImageGenerationResult:
        raise ProviderConfigurationError(NOT_CONFIGURED_MESSAGE)
    async def edit(
        self, image: bytes, prompt: str, mask: bytes | None = None, **kwargs
    ) -> ImageGenerationResult:
        raise ProviderConfigurationError(NOT_CONFIGURED_MESSAGE)
    async def health_check(self) -> bool:
        return False
