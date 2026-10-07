"""A deterministic, dependency-free provider used for local development and tests."""
from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from app.models.chat import ChatMessage
from app.providers.base import AIProvider
class MockProvider(AIProvider):
    """Echo-style provider that never calls any external service.
    Useful as the default provider (``AI_PROVIDER=mock``) so the whole stack
    can be run and tested without any API keys.
    """
    name = "mock"
    def __init__(self, model_name: str = "nexa-mock-1") -> None:
        self._model_name = model_name
    @property
    def model_name(self) -> str:
        return self._model_name
    async def generate(self, messages: list[ChatMessage]) -> str:
        last_user_message = self._last_user_content(messages)
        # Simulate a tiny bit of async work so behavior mirrors a real backend.
        await asyncio.sleep(0)
        return f"[mock:{self._model_name}] You said: {last_user_message}"
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        text = await self.generate(messages)
        for word in text.split(" "):
            await asyncio.sleep(0)
            yield word + " "
    async def health_check(self) -> bool:
        return True
    @staticmethod
    def _last_user_content(messages: list[ChatMessage]) -> str:
        for message in reversed(messages):
            if message.role.value == "user":
                return message.content
        return ""
