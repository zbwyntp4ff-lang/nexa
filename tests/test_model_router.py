"""Intelligent Model Router — Auto/manual policy, no silent mock, secrets hygiene."""
from __future__ import annotations
import pytest
from app.config.settings import Settings
from app.gateway.catalog import static_catalog
from app.gateway.model_registry import ModelRegistry, is_safe_model_id
from app.gateway.models import ModelCard, Selection, TaskKind
from app.gateway.policy import ModelSelectionPolicy, infer_task_kind
from app.gateway.gateway import ModelGateway, build_provider_registry
from app.core.secrets import redact_secrets, contains_secret


def _available(provider: str, model_id: str, caps: list[str] | None = None) -> ModelCard:
    return ModelCard(
        provider=provider,
        model_id=model_id,
        display_name=model_id,
        capabilities=caps or ["chat", "simple", "coding", "tools", "reasoning"],
        availability="available",
    )


def test_infer_task_kind_keywords_and_long_doc():
    assert infer_task_kind("please write code for a sorter") == TaskKind.CODING
    assert infer_task_kind("step by step reason about this") == TaskKind.REASONING
    assert infer_task_kind("search the web for news") == TaskKind.RESEARCH
    assert infer_task_kind("keep this local only") == TaskKind.LOCAL
    assert infer_task_kind("hello") == TaskKind.SIMPLE
    assert infer_task_kind("x" * 3000) == TaskKind.REASONING


def test_auto_simple_prefers_available_openrouter_free_before_unavailable_openai():
    policy = ModelSelectionPolicy()
    cards = [
        _available("openrouter", "openrouter/free", ["chat", "simple", "coding", "tools"]),
        ModelCard(
            provider="openai",
            model_id="gpt-4o-mini",
            display_name="GPT-4o mini",
            capabilities=["chat", "simple", "coding"],
            availability="unavailable",
            availability_reason="missing_api_key",
        ),
    ]
    ordered = policy.candidates(TaskKind.SIMPLE, cards, allow_cloud_for_local=False)
    assert ordered
    assert ordered[0].model_id == "openrouter/free"
    assert all(c.provider != "mock" for c in ordered)


def test_auto_never_injects_mock_when_nothing_configured():
    policy = ModelSelectionPolicy()
    cards = [
        ModelCard(
            provider="mock",
            model_id="nexa-mock-1",
            display_name="Mock",
            capabilities=["chat", "simple"],
            availability="available",
        ),
        ModelCard(
            provider="openai",
            model_id="gpt-4o",
            display_name="GPT-4o",
            capabilities=["chat", "reasoning"],
            availability="unavailable",
            availability_reason="missing_api_key",
        ),
    ]
    ordered = policy.candidates(TaskKind.REASONING, cards, allow_cloud_for_local=False)
    assert ordered == []


def test_coding_route_includes_gemini_when_available():
    policy = ModelSelectionPolicy()
    cards = [
        _available("gemini", "gemini-2.0-flash", ["chat", "coding", "tools", "simple"]),
        _available("openai", "gpt-4o-mini", ["chat", "coding", "tools"]),
    ]
    ordered = policy.candidates(TaskKind.CODING, cards, allow_cloud_for_local=False)
    ids = [c.model_id for c in ordered]
    assert "gpt-4o-mini" in ids
    assert "gemini-2.0-flash" in ids


def test_openrouter_model_ids_with_slash_are_safe():
    assert is_safe_model_id("openrouter/free")
    assert is_safe_model_id("google/gemma-4-26b-a4b-it:free")
    assert not is_safe_model_id("../evil")


def test_selection_persists_roundtrip(tmp_path, monkeypatch):
    settings = Settings(AI_PROVIDER="ollama", OPENAI_API_KEY=None, _env_file=None)
    gateway = ModelGateway(
        providers=build_provider_registry(settings),
        models=ModelRegistry(static_catalog()),
        settings=settings,
        selection=Selection(mode="auto", allow_fallback=False),
    )
    sel = gateway.set_selection("openrouter", "openrouter/free", allow_fallback=False)
    assert sel.mode == "manual"
    assert sel.provider == "openrouter"
    assert sel.model_id == "openrouter/free"


def test_secrets_redacted_and_detected():
    sample = "Bearer sk-or-v1-abcdef0123456789abcdef"
    assert "***REDACTED***" in redact_secrets(sample)
    assert contains_secret("sk-ant-abcdefghijklmnop")


@pytest.mark.asyncio
async def test_manual_missing_key_does_not_swap_to_ollama(monkeypatch):
    """Manual OpenAI with no key must fail honestly, not silently use Ollama."""
    from app.models.chat import ChatMessage, ChatRole
    from app.gateway.errors import GatewayError, AUTHENTICATION_ERROR

    settings = Settings(AI_PROVIDER="ollama", OPENAI_API_KEY=None, _env_file=None)
    gateway = ModelGateway(
        providers=build_provider_registry(settings),
        models=ModelRegistry(static_catalog()),
        settings=settings,
        selection=Selection(mode="manual", provider="openai", model_id="gpt-4o-mini", allow_fallback=False),
    )
    gateway._models.set_ollama(["llama3.2:3b"], reachable=True)
    with pytest.raises(GatewayError) as exc:
        await gateway.chat([ChatMessage(role=ChatRole.USER, content="hi")])
    assert exc.value.code == AUTHENTICATION_ERROR


@pytest.mark.asyncio
async def test_local_only_document_routing_overrides_manual_cloud_selection(monkeypatch):
    """A private-document request must not follow a persisted cloud selection."""
    from app.models.chat import ChatMessage, ChatRole

    settings = Settings(AI_PROVIDER="ollama", _env_file=None)
    models = ModelRegistry(static_catalog())
    models.set_ollama(["llama3.2:3b"], reachable=True)
    gateway = ModelGateway(
        providers=build_provider_registry(settings),
        models=models,
        settings=settings,
        selection=Selection(
            mode="manual",
            provider="openai",
            model_id="gpt-4o-mini",
            allow_fallback=True,
        ),
    )

    class FakeLocalProvider:
        name = "ollama"
        model_name = "llama3.2:3b"

        async def chat(self, messages):
            return "local-only answer"

    async def no_refresh(force=False):
        return None

    monkeypatch.setattr(gateway, "refresh_ollama", no_refresh)
    monkeypatch.setattr(gateway, "_open", lambda card: FakeLocalProvider())

    result = await gateway.chat(
        [ChatMessage(role=ChatRole.USER, content="Summarize this private document.")],
        model="auto",
        task_kind=TaskKind.LOCAL,
        allow_fallback=False,
    )

    assert result.provider == "ollama"
    assert result.model_id == "llama3.2:3b"
    assert result.text == "local-only answer"
