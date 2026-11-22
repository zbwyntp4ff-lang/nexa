"""Regression tests for the HEXA 4.5 provider integration."""
from __future__ import annotations

import pytest

from app.config.settings import Settings, SUPPORTED_PROVIDERS
from app.gateway.gateway import build_provider_registry, initial_selection
from app.models.errors import ProviderConfigurationError
from app.providers.hexa_provider import Hexa45Provider


def test_hexa_provider_requires_its_own_endpoint() -> None:
    with pytest.raises(ProviderConfigurationError, match="HEXA_MODEL_URL"):
        Hexa45Provider(base_url=None)


def test_hexa_provider_has_dedicated_identity() -> None:
    provider = Hexa45Provider(
        base_url="http://127.0.0.1:11434",
        model="hexa-4.5",
    )
    assert provider.name == "hexa"
    assert provider.model_name == "hexa-4.5"


def test_hexa_provider_is_supported_and_registered() -> None:
    settings = Settings(
        AI_PROVIDER="hexa",
        HEXA_MODEL_URL="http://127.0.0.1:11434",
        HEXA_MODEL_NAME="hexa-4.5",
        _env_file=None,
    )
    assert "hexa" in SUPPORTED_PROVIDERS
    provider = build_provider_registry(settings).create("hexa", "hexa-4.5")
    assert provider.name == "hexa"
    assert provider.model_name == "hexa-4.5"


def test_hexa_can_be_selected_from_application_settings() -> None:
    settings = Settings(
        AI_PROVIDER="hexa",
        HEXA_MODEL_URL="http://127.0.0.1:11434",
        HEXA_MODEL_NAME="hexa-4.5",
        _env_file=None,
    )
    selection = initial_selection(settings)
    assert selection.provider == "hexa"
    assert selection.model_id == "hexa-4.5"


def test_hexa_catalog_reports_missing_inference_endpoint() -> None:
    from app.gateway.catalog import static_catalog
    from app.gateway.model_registry import ModelRegistry

    registry = ModelRegistry(static_catalog())
    cards = registry.cards(
        openai_configured=False,
        anthropic_configured=False,
        gemini_configured=False,
        openrouter_configured=False,
        hexa_configured=False,
        include_mock=False,
    )
    hexa = next(card for card in cards if card.provider == "hexa")
    assert hexa.availability == "unavailable"
    assert hexa.availability_reason == "missing_model_endpoint"
