"""Anthropic (Claude) backed provider.
Requires ``ANTHROPIC_API_KEY`` to be set. The API key is read once at
construction time and is never logged.
"""
from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from app.models.chat import ChatMessage, ChatRole
from app.models.errors import ModelError, ProviderConfigurationError, ProviderTimeoutError
from app.providers.base import AIProvider
DEFAULT_MAX_TOKENS = 1024
class AnthropicProvider(AIProvider):
    """Provider that delegates chat completion to the Anthropic API."""
    name = "anthropic"
    def __init__(
        self,
        api_key: str | None,
        model: str = "claude-3-5-sonnet-latest",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError(
                "ANTHROPIC_API_KEY is not set. Configure it in your .env file."
            )
        self._model = model
        self._timeout_seconds = timeout_seconds
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderConfigurationError(
                "The 'anthropic' package is required to use AI_PROVIDER=anthropic."
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)
    @property
    def model_name(self) -> str:
        return self._model
    @staticmethod
    def _message_content(message: ChatMessage) -> str | list[dict]:
        if not message.images:
            return message.content
        blocks: list[dict] = [{"type": "text", "text": message.content}]
        for image in message.images:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.mime_type,
                        "data": image.data_base64,
                    },
                }
            )
        return blocks
    def _split_system_and_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str | None, list[dict]]:
        system_parts = [m.content for m in messages if m.role == ChatRole.SYSTEM]
        conversation = [
            {"role": m.role.value, "content": self._message_content(m)}
            for m in messages
            if m.role != ChatRole.SYSTEM
        ]
        system = "\n".join(system_parts) if system_parts else None
        return system, conversation
    async def generate(self, messages: list[ChatMessage]) -> str:
        system, conversation = self._split_system_and_messages(messages)
        kwargs = {
            "model": self._model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": conversation,
        }
        if system:
            kwargs["system"] = system
        try:
            response = await asyncio.wait_for(
                self._client.messages.create(**kwargs),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"Anthropic request failed: {exc}") from exc
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        content = "".join(text_blocks)
        if not content:
            raise ModelError("Anthropic returned an empty response.")
        return content
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        system, conversation = self._split_system_and_messages(messages)
        kwargs = {
            "model": self._model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": conversation,
        }
        if system:
            kwargs["system"] = system
        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"Anthropic streaming request failed: {exc}") from exc
    async def health_check(self) -> bool:
        try:
            await asyncio.wait_for(
                self._client.messages.create(
                    model=self._model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ping"}],
                ),
                timeout=5,
            )
            return True
        except Exception:  # noqa: BLE001
            return False
