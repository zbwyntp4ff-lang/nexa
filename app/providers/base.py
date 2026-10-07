"""The ``AIProvider`` interface that every model backend must implement.
NEXA Core depends only on this abstraction, never on a concrete provider, so
new backends (including a future first-party ``nexa`` provider) can be added
without touching the core.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from app.models.chat import ChatMessage
class AIProvider(ABC):
    """Abstract base class for all AI model providers."""
    #: Machine-readable name used for configuration/logging, e.g. ``"mock"``.
    name: str = "base"
    @abstractmethod
    async def generate(self, messages: list[ChatMessage]) -> str:
        """Generate a single, complete response for the given conversation.
        Args:
            messages: Full conversation history, oldest message first, with
                the user's latest message last.
        Returns:
            The assistant's response text.
        Raises:
            app.models.errors.ModelError: If the provider fails to generate
                a response.
            app.models.errors.ProviderTimeoutError: If the call times out.
        """
    @abstractmethod
    def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        """Generate a response incrementally, yielding text chunks.
        Args:
            messages: Full conversation history, oldest message first.
        Yields:
            Successive text chunks that, concatenated, form the full
            response.
        """
    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
    @property
    @abstractmethod
    def model_name(self) -> str:
        """The concrete model identifier this provider is configured to use."""
    async def chat(self, messages: list[ChatMessage]) -> str:
        """Unified chat entry point. Delegates to :meth:`generate`.
        Model Gateway and agents call ``chat()`` so they do not depend on a
        provider-specific SDK. Existing callers of ``generate()`` keep working.
        """
        return await self.generate(messages)
    def model_info(self) -> dict[str, str]:
        """Minimal provider/model identity. Never includes credentials."""
        return {"provider": self.name, "model_id": self.model_name}
