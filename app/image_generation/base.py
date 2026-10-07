"""The ``ImageGenerationProvider`` interface.
Prepared as an extension point for future image-model integrations - NEXA
does not implement its own image generation model. If no provider is
configured, :class:`app.image_generation.not_configured.NotConfiguredImageGenerationProvider`
is used, which fails clearly rather than fabricating a fake image.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from app.image_generation.models import ImageGenerationResult
class ImageGenerationProvider(ABC):
    name: str = "base"
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> ImageGenerationResult:
        """Generate one or more images from a text prompt.
        Raises:
            app.models.errors.ProviderConfigurationError: If no real
                provider is configured.
            app.models.errors.ModelError: If generation fails.
        """
    @abstractmethod
    async def edit(
        self, image: bytes, prompt: str, mask: bytes | None = None, **kwargs
    ) -> ImageGenerationResult:
        """Edit an existing image according to ``prompt`` (optionally masked).
        Raises:
            app.models.errors.ProviderConfigurationError: If no real
                provider is configured.
            app.models.errors.ModelError: If the edit fails.
        """
    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
