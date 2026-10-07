"""Dedicated tests for the error hierarchy, HTTP status mapping, and the
requirement that secrets are never logged.
"""
from __future__ import annotations
import logging
import pytest
from fastapi.testclient import TestClient
from app.api.deps import get_nexa_core
from app.core.logging_config import SecretRedactionFilter
from app.main import app
from app.models.errors import (
    EmptyMessageError,
    MessageTooLongError,
    ModelError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    UnknownProviderError,
)
def test_empty_message_error_default_message():
    error = EmptyMessageError()
    assert "empty" in error.message.lower()
def test_message_too_long_error_reports_lengths():
    error = MessageTooLongError(length=5000, max_length=4000)
    assert "5000" in error.message
    assert "4000" in error.message
def test_unknown_provider_error_lists_available_providers():
    error = UnknownProviderError("banana", available=("mock", "openai"))
    assert "banana" in error.message
    assert "mock" in error.message
    assert "openai" in error.message
def test_provider_configuration_error_message():
    error = ProviderConfigurationError("OPENAI_API_KEY is not set.")
    assert "OPENAI_API_KEY" in error.message
def test_secret_redaction_filter_scrubs_openai_key():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="using api key sk-abcdefghijklmnopqrstuvwxyz",
        args=(),
        exc_info=None,
    )
    SecretRedactionFilter().filter(record)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in record.msg
    assert "REDACTED" in record.msg
def test_secret_redaction_filter_scrubs_anthropic_key():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="key=%s",
        args=("sk-ant-abcdefghijklmnopqrstuvwxyz",),
        exc_info=None,
    )
    SecretRedactionFilter().filter(record)
    assert record.args[0] == "***REDACTED***"
@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
def test_unknown_provider_configured_returns_error_without_stack_trace(
    client: TestClient, monkeypatch
):
    from app.config.settings import get_settings
    monkeypatch.setenv("AI_PROVIDER", "not-a-real-provider")
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
    response = client.get("/api/v1/model")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "UnknownProviderError"
    assert "Traceback" not in body["message"]
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
def test_missing_provider_credentials_returns_503(client: TestClient, monkeypatch):
    from app.config.settings import get_settings
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
    response = client.get("/api/v1/model")
    assert response.status_code == 503
    assert response.json()["error"] == "ProviderConfigurationError"
    get_settings.cache_clear()
    get_nexa_core.cache_clear()
