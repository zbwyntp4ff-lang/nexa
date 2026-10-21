"""Tests for application configuration."""
from __future__ import annotations
from app.config.settings import Settings, get_settings
def test_default_provider_is_mock(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    get_settings.cache_clear()
    # Construct without inheriting a developer .env AI_PROVIDER=ollama override.
    settings = Settings(_env_file=None)
    assert settings.ai_provider == "mock"
def test_provider_read_from_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "OpenAI")
    get_settings.cache_clear()
    settings = get_settings()
    # Provider names are normalized to lowercase.
    assert settings.ai_provider == "openai"
def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
def test_masked_dict_redacts_api_keys():
    settings = Settings(
        AI_PROVIDER="openai",
        OPENAI_API_KEY="sk-super-secret-value",
        ANTHROPIC_API_KEY="sk-ant-super-secret-value",
    )
    masked = settings.masked_dict()
    assert masked["openai_api_key"] == "***REDACTED***"
    assert masked["anthropic_api_key"] == "***REDACTED***"
    assert "super-secret" not in str(masked)
def test_masked_dict_handles_missing_keys():
    settings = Settings(AI_PROVIDER="mock", OPENAI_API_KEY=None, ANTHROPIC_API_KEY=None)
    masked = settings.masked_dict()
    assert masked["openai_api_key"] is None
    assert masked["anthropic_api_key"] is None
