"""Tests for the first-party HEXA 4.5 server adapter."""
from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.gateway.gateway import build_provider_registry, initial_selection
from app.models.errors import ProviderConfigurationError
from app.providers.hexa_provider import Hexa45Provider


def test_hexa_provider_requires_server_url():
    with pytest.raises(ProviderConfigurationError, match="HEXA_MODEL_URL"):
        Hexa45Provider(base_url=None)


def test_hexa_provider_uses_dedicated_identity():
    provider = Hexa45Provider(base_url="http://127.0.0.1:11434", model="hexa-4.5")
    assert provider.name == "hexa"
    assert provider.model_name == "hexa-4.5"


def test_hexa_provider_is_registered():
    settings = Settings(AI_PROVIDER="hexa", HEXA_MODEL_URL="http://127.0.0.1:11434", HEXA_MODEL_NAME="hexa-4.5", _env_file=None)
    provider = build_provider_registry(settings).create("hexa", "hexa-4.5")
    assert provider.name == "hexa"
    assert provider.model_name == "hexa-4.5"


def test_hexa_can_be_selected_by_default():
    settings = Settings(AI_PROVIDER="hexa", HEXA_MODEL_URL="http://127.0.0.1:11434", HEXA_MODEL_NAME="hexa-4.5", _env_file=None)
    selection = initial_selection(settings)
    assert selection.provider == "hexa"
    assert selection.model_id == "hexa-4.5"
