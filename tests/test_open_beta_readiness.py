"""Open public beta readiness — guards, kill switch, concurrency, auth recovery."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agent.concurrency import (
    AgentBusyError,
    reset_agent_concurrency,
    try_acquire_agent_slot,
    release_agent_slot,
)
from app.config.production_guards import (
    ProductionConfigError,
    assert_durable_production,
    is_public_cloud,
    validate_production_settings,
)
from app.config.settings import Settings, get_settings
from app.gateway.errors import GatewayError, MODEL_UNAVAILABLE
def _public_beta_env(monkeypatch, **extra: str) -> Settings:
    monkeypatch.setenv("NEXA_PUBLIC_BETA", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NEXA_STORAGE_MODE", "persistent")
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "false")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("AUTH_SINGLE_USER", "false")
    monkeypatch.setenv("MEMORY_BACKEND", "sql")
    monkeypatch.setenv("AUTH_PUBLIC_BASE_URL", "https://beta.nexa.example")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://beta.nexa.example")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "noreply@nexa.example")
    for k, v in extra.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    return Settings(_env_file=None)


def test_public_beta_profile_requires_safe_cloud(monkeypatch):
    settings = _public_beta_env(monkeypatch)
    assert is_public_cloud(settings) is True
    assert validate_production_settings(settings) == []


def test_public_beta_rejects_free_model_and_desktop(monkeypatch):
    settings = _public_beta_env(
        monkeypatch,
        OPENROUTER_MODEL="openrouter/free",
        NEXA_LOCAL_DESKTOP="1",
        AUTH_SKIP_EMAIL_VERIFICATION="true",
    )
    problems = validate_production_settings(settings)
    assert any("OPENROUTER_MODEL" in p for p in problems)
    assert any("NEXA_LOCAL_DESKTOP" in p for p in problems)
    assert any("AUTH_SKIP_EMAIL_VERIFICATION" in p for p in problems)
    with pytest.raises(ProductionConfigError):
        assert_durable_production(settings)


def test_public_beta_rejects_single_user_and_ephemeral(monkeypatch):
    settings = _public_beta_env(
        monkeypatch,
        AUTH_SINGLE_USER="true",
        NEXA_STORAGE_MODE="ephemeral",
    )
    problems = validate_production_settings(settings)
    assert any("AUTH_SINGLE_USER" in p for p in problems)
    assert any("persistent" in p for p in problems)


def test_public_beta_requires_smtp(monkeypatch):
    settings = _public_beta_env(
        monkeypatch,
        EMAIL_PROVIDER="console",
        SMTP_HOST="",
        EMAIL_FROM="",
    )
    problems = validate_production_settings(settings)
    assert any("EMAIL_PROVIDER" in p for p in problems)
    assert any("SMTP_HOST" in p for p in problems)
    assert any("EMAIL_FROM" in p for p in problems)


def test_resend_and_forgot_do_not_enumerate(tmp_path, monkeypatch):
    """Known vs unknown emails must share the same public response fields."""
    from app.api.deps import get_auth_service, get_auth_store, get_nexa_core
    from app.auth.email import EmailService
    from app.auth.service import AuthService
    from app.auth.store import AuthStore
    from app.main import app

    monkeypatch.setenv("AUTH_STORE_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("AUTH_LEGAL_DIR", str(tmp_path / "legal"))
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "false")
    monkeypatch.setenv("TOKENS_ENFORCE", "false")
    monkeypatch.setenv("AUTH_BOOTSTRAP_FIRST_OWNER", "true")
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_nexa_core.cache_clear()

    class Cap(EmailService):
        def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
            return None

    store = AuthStore(tmp_path / "auth.json")
    service = AuthService(
        store,
        Cap(),
        code_ttl_seconds=900,
        resend_cooldown_seconds=60,
        max_verify_attempts=5,
        session_ttl_seconds=3600,
        app_name="NEXA Test",
        bootstrap_first_owner=True,
        single_user=False,
        skip_email_verification=False,
    )
    # Seed a verified user without going through email delivery.
    from app.auth.models import UserRecord
    from app.auth.passwords import hash_password

    user = UserRecord(
        id="u-enum",
        email="known@nexa.test",
        username="knownuser",
        password_hash=hash_password("Secret123"),
        first_name="K",
        last_name="N",
        email_verified=True,
        is_active=True,
    )
    store.save_user(user)
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_auth_store] = lambda: store
    client = TestClient(app)
    try:
        unknown_forgot = client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@nexa.test"}
        )
        known_forgot = client.post(
            "/api/v1/auth/forgot-password", json={"email": "known@nexa.test"}
        )
        assert unknown_forgot.status_code == 200
        assert known_forgot.status_code == 200
        u, k = unknown_forgot.json(), known_forgot.json()
        assert set(u.keys()) == set(k.keys())
        assert u.get("code_expires_at") is None
        assert k.get("code_expires_at") is None

        unknown_resend = client.post(
            "/api/v1/auth/resend-code", json={"email": "nobody@nexa.test"}
        )
        known_resend = client.post(
            "/api/v1/auth/resend-code", json={"email": "known@nexa.test"}
        )
        assert unknown_resend.status_code == 200
        assert known_resend.status_code == 200
        ur, kr = unknown_resend.json(), known_resend.json()
        assert ur["sent"] is True and kr["sent"] is True
        assert ur["already_verified"] is False and kr["already_verified"] is False
        assert ur.get("code_expires_at") is None
        assert kr.get("code_expires_at") is None
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        get_auth_store.cache_clear()
        get_auth_service.cache_clear()


@pytest.mark.asyncio
async def test_agent_parallel_cap(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_PARALLEL_PER_USER", "1")
    get_settings.cache_clear()
    reset_agent_concurrency()
    s1 = await try_acquire_agent_slot("user-a")
    assert s1 is not None
    with pytest.raises(AgentBusyError):
        await try_acquire_agent_slot("user-a")
    release_agent_slot(s1)
    s2 = await try_acquire_agent_slot("user-a")
    release_agent_slot(s2)
    reset_agent_concurrency()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_kill_switch_blocks_gateway(monkeypatch):
    monkeypatch.setenv("NEXA_AI_KILL_SWITCH", "true")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.ai_kill_switch is True
    from app.gateway.gateway import build_model_gateway

    from app.models.chat import ChatMessage, ChatRole

    gw = build_model_gateway(settings)
    with pytest.raises(GatewayError) as ei:
        await gw.chat([ChatMessage(role=ChatRole.USER, content="hi")])
    assert ei.value.code == MODEL_UNAVAILABLE
    assert "disabled" in ei.value.message.lower()
    monkeypatch.setenv("NEXA_AI_KILL_SWITCH", "false")
    get_settings.cache_clear()


def test_forgot_and_reset_password_flow(tmp_path, monkeypatch):
    """Recovery path exists for open beta self-serve users."""
    from app.api.deps import get_auth_service, get_auth_store, get_nexa_core
    from app.auth.email import EmailService
    from app.auth.service import AuthService
    from app.auth.store import AuthStore
    from app.main import app
    import re

    monkeypatch.setenv("AUTH_STORE_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("AUTH_LEGAL_DIR", str(tmp_path / "legal"))
    monkeypatch.setenv("AUTH_SKIP_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("TOKENS_ENFORCE", "false")
    monkeypatch.setenv("AUTH_BOOTSTRAP_FIRST_OWNER", "true")
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_nexa_core.cache_clear()

    class Cap(EmailService):
        def __init__(self) -> None:
            self.messages: list[tuple[str, str, str]] = []

        def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
            self.messages.append((to, subject, text_body))

        def last_code(self) -> str:
            m = re.search(r"\b(\d{6})\b", self.messages[-1][2])
            assert m
            return m.group(1)

    mail = Cap()
    store = AuthStore(tmp_path / "auth.json")
    service = AuthService(
        store,
        mail,
        code_ttl_seconds=900,
        resend_cooldown_seconds=1,
        max_verify_attempts=5,
        session_ttl_seconds=3600,
        app_name="NEXA Test",
        bootstrap_first_owner=True,
        single_user=False,
        skip_email_verification=True,
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_auth_store] = lambda: store
    client = TestClient(app)
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "A",
                "last_name": "B",
                "username": "resetme",
                "email": "reset@nexa.test",
                "password": "Secret123",
                "confirm_password": "Secret123",
                "accept_terms": True,
                "accept_privacy": True,
                "accept_license": True,
            },
        )
        assert reg.status_code in (200, 201), reg.text
        forgot = client.post("/api/v1/auth/forgot-password", json={"email": "reset@nexa.test"})
        assert forgot.status_code == 200
        assert "reset" in forgot.json()["message"].lower() or "sent" in forgot.json()["message"].lower()
        code = mail.last_code()
        reset = client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": "reset@nexa.test",
                "code": code,
                "password": "NewSecret123",
                "confirm_password": "NewSecret123",
            },
        )
        assert reset.status_code == 200, reset.text
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "reset@nexa.test", "password": "NewSecret123"},
        )
        assert login.status_code == 200, login.text
        token = login.cookies.get("nexa_session")
        assert token
        out = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert out.status_code == 200
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        get_auth_store.cache_clear()
        get_auth_service.cache_clear()
