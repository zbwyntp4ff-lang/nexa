"""Production config guards — durable public launch only."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config.production_guards import (
    ProductionConfigError,
    assert_durable_production,
    is_durable_production,
    validate_production_settings,
)
from app.config.settings import Settings, get_settings
from app.main import app


def _settings(**kwargs) -> Settings:
    """Build Settings without picking up a local .env as the source of truth."""
    return Settings(_env_file=None, **kwargs)


def test_ephemeral_production_does_not_hard_fail():
    s = _settings(
        environment="production",
        NEXA_STORAGE_MODE="ephemeral",
        AUTH_SKIP_EMAIL_VERIFICATION=True,
        AI_PROVIDER="mock",
        TOKENS_ENFORCE=True,
    )
    assert is_durable_production(s) is False
    assert validate_production_settings(s) == []
    assert_durable_production(s)  # no raise


def test_durable_production_rejects_tokens_enforce_false():
    s = _settings(
        environment="production",
        NEXA_STORAGE_MODE="persistent",
        AUTH_SKIP_EMAIL_VERIFICATION=False,
        AUTH_COOKIE_SECURE=True,
        TOKENS_ENFORCE=False,
        AI_PROVIDER="openai",
        OPENAI_API_KEY="sk-test",
        AUTH_PUBLIC_BASE_URL="https://app.example.com",
        CORS_ALLOWED_ORIGINS="https://app.example.com",
        MEMORY_BACKEND="sql",
    )
    problems = validate_production_settings(s)
    assert any("TOKENS_ENFORCE" in p for p in problems)
    with pytest.raises(ProductionConfigError):
        assert_durable_production(s)


def test_durable_production_rejects_unsafe_defaults():
    s = _settings(
        environment="production",
        NEXA_STORAGE_MODE="persistent",
        AUTH_SKIP_EMAIL_VERIFICATION=True,
        AUTH_COOKIE_SECURE=False,
        TOKENS_ENFORCE=False,
        AI_PROVIDER="mock",
        AUTH_PUBLIC_BASE_URL="",
        CORS_ALLOWED_ORIGINS="http://localhost:3000",
        MEMORY_BACKEND="json",
    )
    problems = validate_production_settings(s)
    assert len(problems) >= 4
    with pytest.raises(ProductionConfigError):
        assert_durable_production(s)


def test_durable_production_ok_when_hardened(monkeypatch):
    # Flag checks read os.environ directly — clear host desktop flags.
    monkeypatch.delenv("NEXA_LOCAL_DESKTOP", raising=False)
    monkeypatch.delenv("NEXA_ELECTRON_ALLOW_LAN_BIND", raising=False)
    monkeypatch.delenv("NEXA_ALLOW_PACKAGED_DEVTOOLS", raising=False)
    s = _settings(
        environment="production",
        NEXA_STORAGE_MODE="persistent",
        AUTH_SKIP_EMAIL_VERIFICATION=False,
        AUTH_COOKIE_SECURE=True,
        TOKENS_ENFORCE=True,
        AI_PROVIDER="openai",
        OPENAI_API_KEY="sk-test",
        AUTH_PUBLIC_BASE_URL="https://app.example.com",
        CORS_ALLOWED_ORIGINS="https://app.example.com",
        MEMORY_BACKEND="sql",
        WORKFLOWS_ENABLED=False,
        EMAIL_PROVIDER="smtp",
        SMTP_HOST="smtp.example.com",
        EMAIL_FROM="noreply@example.com",
    )
    assert is_durable_production(s) is True
    assert validate_production_settings(s) == []
    assert_durable_production(s)


def test_development_skips_guards():
    s = _settings(environment="development", NEXA_STORAGE_MODE="persistent")
    assert validate_production_settings(s) == []


def test_unauthenticated_api_denied_when_tokens_enforced(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """No accidental anonymous access when TOKENS_ENFORCE=true."""
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("AUTH_STORE_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'nexa.db'}")
    get_settings.cache_clear()
    client = TestClient(app)
    assert client.get("/api/v1/memory").status_code in (401, 403)
    assert client.get("/api/v1/conversations").status_code in (401, 403)
    assert client.get("/api/v1/plugins").status_code in (401, 403)
    assert client.post("/api/v1/chat", json={"message": "hi"}).status_code in (
        401,
        403,
    )
    assert client.post(
        "/api/v1/workflows", json={"goal": "x"}
    ).status_code in (401, 403, 503)
    get_settings.cache_clear()


def test_workflows_disabled_returns_503(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TOKENS_ENFORCE", "false")
    monkeypatch.setenv("WORKFLOWS_ENABLED", "false")
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'nexa.db'}")
    get_settings.cache_clear()
    client = TestClient(app)
    r = client.post("/api/v1/workflows", json={"goal": "should fail"})
    assert r.status_code == 503
    body = r.json()
    assert body.get("error") in ("FeatureDisabled", "FeatureDisabledError") or "disabled" in (
        body.get("message") or body.get("detail") or ""
    ).lower()
    get_settings.cache_clear()
