"""Cloud + local provider switching: honest errors, no silent mock fallback."""
from __future__ import annotations
import pytest
from app.config.settings import Settings
from app.gateway.catalog import static_catalog
from app.gateway.errors import AUTHENTICATION_ERROR, GatewayError
from app.gateway.gateway import ModelGateway, build_provider_registry, initial_selection
from app.gateway.model_registry import ModelRegistry
from app.gateway.models import Selection, TaskKind
from app.gateway.policy import ModelSelectionPolicy
from app.models.chat import ChatMessage, ChatRole
from app.models.errors import ProviderConfigurationError, UnknownProviderError
from app.providers.factory import ProviderFactory
from app.providers.gemini_provider import GeminiProvider
from app.providers.openrouter_provider import OpenRouterProvider


def _settings(**overrides) -> Settings:
    base = dict(
        AI_PROVIDER="ollama",
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
        GEMINI_API_KEY=None,
        GOOGLE_API_KEY=None,
        OPENROUTER_API_KEY=None,
        ALLOW_MODEL_FALLBACK="false",
    )
    base.update(overrides)
    return Settings(**base)


def _gateway(settings: Settings, *, selection: Selection | None = None) -> ModelGateway:
    return ModelGateway(
        providers=build_provider_registry(settings),
        models=ModelRegistry(static_catalog()),
        settings=settings,
        policy=ModelSelectionPolicy(),
        selection=selection,
    )


def test_factory_openai_missing_key_raises():
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create(_settings(AI_PROVIDER="openai"))


def test_factory_anthropic_missing_key_raises():
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create(_settings(AI_PROVIDER="anthropic"))


def test_factory_gemini_missing_key_raises():
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create(_settings(AI_PROVIDER="gemini"))


def test_factory_openrouter_missing_key_raises():
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory.create(_settings(AI_PROVIDER="openrouter"))


def test_factory_unknown_provider():
    with pytest.raises(UnknownProviderError):
        ProviderFactory.create(_settings(AI_PROVIDER="not-a-provider"))


def test_gemini_accepts_google_api_key_alias():
    settings = _settings(GOOGLE_API_KEY="AIzaSyDummyKeyForUnitTestOnly123456")
    provider = GeminiProvider(api_key=settings.resolved_gemini_api_key, model="gemini-2.0-flash")
    assert provider.name == "gemini"
    assert provider.model_name == "gemini-2.0-flash"


def test_openrouter_provider_requires_key():
    with pytest.raises(ProviderConfigurationError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key=None)


def test_masked_dict_redacts_cloud_keys():
    settings = _settings(
        OPENAI_API_KEY="sk-test-secret-key-abcdefghij",
        ANTHROPIC_API_KEY="sk-ant-secret-key-abcdefghij",
        GEMINI_API_KEY="AIzaSyDummyKeyForUnitTestOnly123456",
        OPENROUTER_API_KEY="sk-or-v1-secret-abcdefghij",
    )
    masked = settings.masked_dict()
    assert masked["openai_api_key"] == "***REDACTED***"
    assert masked["anthropic_api_key"] == "***REDACTED***"
    assert masked["gemini_api_key"] == "***REDACTED***"
    assert masked["openrouter_api_key"] == "***REDACTED***"


def test_catalog_marks_cloud_unavailable_without_keys():
    registry = ModelRegistry(static_catalog())
    cards = registry.cards(
        openai_configured=False,
        anthropic_configured=False,
        gemini_configured=False,
        openrouter_configured=False,
        include_mock=False,
    )
    by_provider = {c.provider for c in cards if c.provider != "ollama"}
    assert "openai" in by_provider
    assert "anthropic" in by_provider
    assert "gemini" in by_provider
    assert "openrouter" in by_provider
    for card in cards:
        if card.provider in ("openai", "anthropic", "gemini", "openrouter"):
            assert card.availability == "unavailable"
            assert card.availability_reason == "missing_api_key"


@pytest.mark.asyncio
async def test_gateway_openai_selection_without_key_raises_auth_error():
    settings = _settings(AI_PROVIDER="openai")
    gateway = _gateway(
        settings,
        selection=Selection(mode="manual", provider="openai", model_id="gpt-4o-mini"),
    )
    with pytest.raises(GatewayError) as exc_info:
        await gateway.chat([ChatMessage(role=ChatRole.USER, content="hello")])
    assert exc_info.value.code == AUTHENTICATION_ERROR
    assert "OpenAI" in str(exc_info.value) or "OPENAI" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gateway_gemini_missing_key_async():
    settings = _settings(AI_PROVIDER="ollama")
    gateway = _gateway(
        settings,
        selection=Selection(mode="manual", provider="gemini", model_id="gemini-2.0-flash"),
    )
    with pytest.raises(GatewayError) as exc_info:
        await gateway.chat([ChatMessage(role=ChatRole.USER, content="hi")])
    assert exc_info.value.code == AUTHENTICATION_ERROR
    assert exc_info.value.provider == "gemini"


@pytest.mark.asyncio
async def test_auto_policy_does_not_silent_mock_when_cloud_unconfigured():
    settings = _settings(AI_PROVIDER="ollama")
    gateway = _gateway(settings, selection=Selection(mode="auto", allow_fallback=False))
    gateway._models.set_ollama([], reachable=False)
    cards = gateway._cards()
    assert all(c.provider != "mock" for c in cards)
    ordered = ModelSelectionPolicy().candidates(TaskKind.SIMPLE, cards, allow_cloud_for_local=False)
    assert all(c.provider != "mock" for c in ordered)


@pytest.mark.asyncio
async def test_switch_selection_openai_to_ollama():
    settings = _settings(AI_PROVIDER="ollama", OPENAI_API_KEY="sk-test-not-used-for-selection")
    gateway = _gateway(settings)
    sel = gateway.set_selection("openai", "gpt-4o-mini", allow_fallback=False)
    assert sel.mode == "manual"
    assert sel.provider == "openai"
    assert sel.model_id == "gpt-4o-mini"
    sel2 = gateway.set_selection("ollama", "llama3.2:3b", allow_fallback=False)
    assert sel2.provider == "ollama"
    assert sel2.model_id == "llama3.2:3b"


def test_initial_selection_maps_cloud_providers():
    s = _settings(AI_PROVIDER="gemini", GEMINI_MODEL="gemini-1.5-pro", GEMINI_API_KEY="x")
    sel = initial_selection(s)
    assert sel.provider == "gemini"
    assert sel.model_id == "gemini-1.5-pro"
    s2 = _settings(AI_PROVIDER="openrouter", OPENROUTER_MODEL="openai/gpt-4o-mini", OPENROUTER_API_KEY="x")
    sel2 = initial_selection(s2)
    assert sel2.provider == "openrouter"
    assert sel2.model_id == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_list_models_never_includes_api_keys():
    settings = _settings(OPENAI_API_KEY="sk-secret-must-not-leak-abcdefgh")
    gateway = _gateway(settings)
    cards = await gateway.list_models(include_mock=False)
    blob = " ".join(f"{c.provider}:{c.model_id}:{c.display_name}:{c.availability_reason}" for c in cards)
    assert "sk-secret" not in blob
