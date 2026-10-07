"""OpenAI-backed vision provider.
Uses a vision-capable chat completion model (e.g. ``gpt-4o-mini``) with the
image passed as a base64 data URI. Requires ``OPENAI_API_KEY``.
"""
from __future__ import annotations
import asyncio
import base64
from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.vision.base import VisionProvider
from app.vision.models import VisionAnalysisResult
DEFAULT_PROMPT = "Describe this image in detail, structured as a short paragraph."
class OpenAIVisionProvider(VisionProvider):
    name = "openai"
    def __init__(
        self,
        api_key: str | None,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is not set. Configure it in your .env file to use VISION_PROVIDER=openai."
            )
        self._model = model
        self._timeout_seconds = timeout_seconds
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderConfigurationError(
                "The 'openai' package is required to use VISION_PROVIDER=openai."
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
    async def analyze(
        self, image: bytes, mime_type: str, prompt: str | None = None
    ) -> VisionAnalysisResult:
        if not image:
            raise ModelError("Image data must not be empty.")
        data_uri = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt or DEFAULT_PROMPT},
                                {"type": "image_url", "image_url": {"url": data_uri}},
                            ],
                        }
                    ],
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"OpenAI vision request failed: {exc}") from exc
        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice and choice.message else None
        if not content:
            raise ModelError("OpenAI vision returned an empty response.")
        return VisionAnalysisResult(
            description=content,
            provider=self.name,
            model=self._model,
            raw={"prompt": prompt or DEFAULT_PROMPT},
        )
    async def health_check(self) -> bool:
        try:
            await asyncio.wait_for(self._client.models.list(), timeout=5)
            return True
        except Exception:  # noqa: BLE001
            return False
