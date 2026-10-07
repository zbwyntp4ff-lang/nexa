"""OpenAI-backed provider.
Requires ``OPENAI_API_KEY`` to be set. The API key is read once at
construction time and is never logged (see :mod:`app.core.logging_config`).
"""
from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from app.models.chat import ChatMessage
from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.providers.base import AIProvider
class OpenAIProvider(AIProvider):
    """Provider that delegates chat completion to the OpenAI API."""
    name = "openai"
    def __init__(
        self,
        api_key: str | None,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is not set. Configure it in your .env file."
            )
        self._model = model
        self._timeout_seconds = timeout_seconds
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - dependency always pinned
            raise ProviderConfigurationError(
                "The 'openai' package is required to use AI_PROVIDER=openai."
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
    @property
    def model_name(self) -> str:
        return self._model
    def _to_openai_messages(self, messages: list[ChatMessage]) -> list[dict]:
        result = []
        for m in messages:
            if not m.images:
                result.append({"role": m.role.value, "content": m.content})
                continue
            content = [{"type": "text", "text": m.content}]
            for image in m.images:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image.mime_type};base64,{image.data_base64}"},
                    }
                )
            result.append({"role": m.role.value, "content": content})
        return result
    async def generate(self, messages: list[ChatMessage]) -> str:
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=self._to_openai_messages(messages),
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
            raise ModelError(f"OpenAI request failed: {exc}") from exc
        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice and choice.message else None
        if not content:
            raise ModelError("OpenAI returned an empty response.")
        return content
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=self._to_openai_messages(messages),
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"OpenAI streaming request failed: {exc}") from exc
    async def health_check(self) -> bool:
        try:
            await asyncio.wait_for(self._client.models.list(), timeout=5)
            return True
        except Exception:  # noqa: BLE001
            return False
