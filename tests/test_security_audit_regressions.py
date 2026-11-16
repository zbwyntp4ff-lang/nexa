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
