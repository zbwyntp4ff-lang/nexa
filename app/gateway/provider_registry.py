"""ProviderRegistry — factories for the real provider classes.
Factories are lazy: a missing API key does not crash the process until that
provider is actually selected.
"""
from __future__ import annotations
from collections.abc import Callable
from app.models.errors import UnknownProviderError
from app.providers.base import AIProvider
ProviderFactoryFn = Callable[[str], AIProvider]
class ProviderRegistry:
    """Maps a provider name to a factory ``(model_id) -> AIProvider``."""
    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactoryFn] = {}
    def register(self, name: str, factory: ProviderFactoryFn) -> None:
        self._factories[name.strip().lower()] = factory
    def names(self) -> tuple[str, ...]:
        return tuple(self._factories)
    def create(self, name: str, model_id: str) -> AIProvider:
        key = name.strip().lower()
        factory = self._factories.get(key)
        if factory is None:
            raise UnknownProviderError(key, available=self.names())
        return factory(model_id)
