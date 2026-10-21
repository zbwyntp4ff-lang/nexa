"""Factory that instantiates the configured :class:`AIProvider`.
This is the *only* place in the codebase that knows how to map the
``AI_PROVIDER`` configuration value to a concrete provider class. NEXA Core
depends solely on the ``AIProvider`` interface, keeping it decoupled from any
specific backend.
"""
from __future__ import annotations
from app.config.settings import SUPPORTED_PROVIDERS, Settings
from app.models.errors import UnknownProviderError
from app.providers.base import AIProvider
from app.providers.mock import MockProvider
class ProviderFactory:
    """Creates :class:`AIProvider` instances based on application settings."""
    @staticmethod
    def create(settings: Settings, provider_override: str | None = None) -> AIProvider:
        """Instantiate the provider selected by configuration.
        Args:
            settings: Application settings (holds API keys, model names, ...).
            provider_override: Optional per-request provider name that takes
                precedence over ``settings.ai_provider``.
        Raises:
            app.models.errors.UnknownProviderError: If the requested provider
                name is not recognized.
        """
        provider_name = (provider_override or settings.ai_provider or "mock").strip().lower()
        if provider_name == "mock":
            return MockProvider()
        if provider_name == "openai":
            from app.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                timeout_seconds=settings.request_timeout_seconds,
            )
        if provider_name == "anthropic":
            from app.providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                timeout_seconds=settings.request_timeout_seconds,
            )
        if provider_name == "gemini":
            from app.providers.gemini_provider import GeminiProvider
            return GeminiProvider(
                api_key=settings.resolved_gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.request_timeout_seconds,
            )
        if provider_name == "openrouter":
            from app.providers.openrouter_provider import OpenRouterProvider
            return OpenRouterProvider(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                timeout_seconds=settings.request_timeout_seconds,
                base_url=settings.openrouter_base_url,
            )
        if provider_name == "local":
            from app.providers.local_provider import LocalProvider
            return LocalProvider(
                base_url=settings.local_model_url,
                model=settings.local_model_name,
                timeout_seconds=settings.request_timeout_seconds,
            )
        if provider_name == "ollama":
            from app.providers.ollama_provider import OllamaProvider
            return OllamaProvider(
                base_url=settings.local_model_url,
                model=settings.local_model_name,
                timeout_seconds=settings.request_timeout_seconds,
            )
        raise UnknownProviderError(provider_name, available=SUPPORTED_PROVIDERS)
