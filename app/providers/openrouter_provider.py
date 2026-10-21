"""OpenRouter provider — OpenAI-compatible HTTP API.

Requires ``OPENROUTER_API_KEY``. Keys are never logged. Missing key raises
:class:`ProviderConfigurationError` (no mock / silent fallback).
"""
from __future__ import annotations
from app.providers.openai_provider import OpenAIProvider

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"


class OpenRouterProvider(OpenAIProvider):
    """Thin OpenAI-compatible client pointed at OpenRouter."""

    name = "openrouter"

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_OPENROUTER_MODEL,
        timeout_seconds: float = 30.0,
        *,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            base_url=(base_url or DEFAULT_OPENROUTER_BASE_URL).rstrip("/"),
            provider_name="openrouter",
            missing_key_message=(
                "OPENROUTER_API_KEY is not set. Configure it in your .env file."
            ),
        )
