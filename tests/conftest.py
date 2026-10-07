"""Shared pytest fixtures.
Ensures each test gets a clean settings/provider cache and does not leak
environment variables (or real API keys) between tests. No test in this
suite ever performs a real network call to an external AI provider.
"""
from __future__ import annotations
import os
import pytest
from app.api.deps import get_nexa_core
from app.config.settings import get_settings
_ENV_KEYS = (
    "AI_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "LOCAL_MODEL_URL",
    "LOCAL_MODEL_NAME",
    "MAX_MESSAGE_LENGTH",
    "REQUEST_TIMEOUT_SECONDS",
)
@pytest.fixture(autouse=True)
def _isolated_settings():
    """Reset cached settings/core and restore environment after each test."""
    original = {key: os.environ.get(key) for key in _ENV_KEYS}
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
