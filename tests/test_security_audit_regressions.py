"""Regression tests for security boundaries fixed during the audit."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import app
from app.web.rate_limit import reset_api_rate_limiter


def test_api_rate_limit_does_not_trust_client_supplied_forwarded_for(monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    reset_api_rate_limiter()
    try:
        with TestClient(app) as client:
            first = client.get(
                "/api/v1/status",
                headers={"X-Forwarded-For": "198.51.100.10"},
            )
            second = client.get(
                "/api/v1/status",
                headers={"X-Forwarded-For": "203.0.113.20"},
            )
        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        reset_api_rate_limiter()
        get_settings.cache_clear()


def test_secret_redaction_covers_bearer_assignments_and_private_keys():
    from app.core.secrets import redact_secrets

    bearer = "Bearer " + "abc.def.ghi"
    assignment = "api_key=" + "nexa_test_credential_12345"
    private_key = (
        "-----BEGIN PRIVATE KEY-----\\n"
        "not-a-real-private-key\\n"
        "-----END PRIVATE KEY-----"
    )
    redacted = redact_secrets(f"{bearer} {assignment} {private_key}")
    assert "abc.def.ghi" not in redacted
    assert "nexa_test_credential_12345" not in redacted
    assert "not-a-real-private-key" not in redacted
