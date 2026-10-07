"""OpenAI-backed image generation provider (used when ``IMAGE_PROVIDER=openai``
and ``OPENAI_API_KEY`` is set).
"""
from __future__ import annotations
import asyncio
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.models import ImageGenerationResult
from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
class OpenAIImageGenerationProvider(ImageGenerationProvider):
    name = "openai"
    def __init__(
        self,
        api_key: str | None,
        model: str = "dall-e-3",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("Image generation provider is not configured.")
        self._model = model
        self._timeout_seconds = timeout_seconds
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderConfigurationError(
                "The 'openai' package is required to use IMAGE_PROVIDER=openai."
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
    async def generate(self, prompt: str, **kwargs) -> ImageGenerationResult:
        size = kwargs.get("size", "1024x1024")
        n = kwargs.get("n", 1)
        try:
            response = await asyncio.wait_for(
                self._client.images.generate(model=self._model, prompt=prompt, size=size, n=n),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"OpenAI image generation failed: {exc}") from exc
        images = [item.url or item.b64_json for item in response.data]
        image_format = "url" if response.data and response.data[0].url else "b64_json"
        return ImageGenerationResult(
            provider=self.name, model=self._model, images=images, format=image_format
        )
    async def edit(
        self, image: bytes, prompt: str, mask: bytes | None = None, **kwargs
    ) -> ImageGenerationResult:
        try:
            response = await asyncio.wait_for(
                self._client.images.edit(
                    model=self._model,
                    image=image,
                    mask=mask,
                    prompt=prompt,
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"OpenAI image edit failed: {exc}") from exc
        images = [item.url or item.b64_json for item in response.data]
        image_format = "url" if response.data and response.data[0].url else "b64_json"
        return ImageGenerationResult(
            provider=self.name, model=self._model, images=images, format=image_format
        )
    async def health_check(self) -> bool:
        try:
            await asyncio.wait_for(self._client.models.list(), timeout=5)
            return True
        except Exception:  # noqa: BLE001
            return False
