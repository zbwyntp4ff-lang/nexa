"""Static model catalog.
Context windows and capability tags are configuration for routing. They are
not measurements and they are not a ranking.
"""
from __future__ import annotations
from app.gateway.models import ModelCard
# Same configured context for every model in a provider family so the number
# cannot be read as "this model is larger, therefore better".
_OPENAI_CONTEXT = 128_000
_ANTHROPIC_CONTEXT = 200_000
def static_catalog() -> list[ModelCard]:
    return [
        ModelCard(
            provider="openai",
            model_id="gpt-4o",
            display_name="GPT-4o",
            capabilities=["chat", "reasoning", "coding", "tools", "vision"],
            context_window=_OPENAI_CONTEXT,
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
        ),
        ModelCard(
            provider="openai",
            model_id="gpt-4o-mini",
            display_name="GPT-4o mini",
            capabilities=["chat", "coding", "tools", "vision"],
            context_window=_OPENAI_CONTEXT,
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
        ),
        ModelCard(
            provider="openai",
            model_id="gpt-4.1-mini",
            display_name="GPT-4.1 mini",
            capabilities=["chat", "simple", "coding"],
            context_window=_OPENAI_CONTEXT,
            supports_vision=False,
            supports_tools=False,
            supports_streaming=True,
        ),
        ModelCard(
            provider="anthropic",
            model_id="claude-opus-4-20250514",
            display_name="Claude Opus 4",
            capabilities=["chat", "reasoning", "coding", "tools", "vision"],
            context_window=_ANTHROPIC_CONTEXT,
            supports_vision=True,
            supports_tools=True,
            supports_streaming=True,
        ),
        ModelCard(
            provider="anthropic",
            model_id="claude-sonnet-4-20250514",
            display_name="Claude Sonnet 4",
            capabilities=["chat", "simple", "coding", "tools"],
            context_window=_ANTHROPIC_CONTEXT,
            supports_vision=False,
            supports_tools=True,
            supports_streaming=True,
        ),
        ModelCard(
            provider="anthropic",
            model_id="claude-3-5-haiku-latest",
            display_name="Claude 3.5 Haiku",
            capabilities=["chat", "coding", "tools"],
            context_window=_ANTHROPIC_CONTEXT,
            supports_vision=False,
            supports_tools=True,
            supports_streaming=True,
        ),
        ModelCard(
            provider="mock",
            model_id="nexa-mock-1",
            display_name="NEXA Mock",
            capabilities=["chat", "simple", "coding", "tools", "reasoning"],
            context_window=8_000,
            supports_vision=False,
            supports_tools=False,
            supports_streaming=True,
            availability="available",
        ),
    ]
