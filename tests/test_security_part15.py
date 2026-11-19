"""Part 15 — regression tests for confirmed security fixes."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_auth_store
from app.auth.email import EmailService
from app.auth.errors import PasskeyError, SessionInvalidError, UnauthorizedError, ValidationAuthError
from app.auth.models import EmailVerificationRecord, UserRecord, utcnow
from app.auth.oauth import OAuthProfile
from app.auth.passwords import hash_code, hash_password
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.config.settings import get_settings
from app.core.secrets import contains_secret
from app.main import app
from app.models.errors import SSRFProtectionError
from app.plugins.adapters.github import _safe_owner_repo
from app.plugins.errors import PluginValidationError
from app.plugins.manager import get_plugin_manager
from app.tools.registry import get_default_tool_registry
from app.web.security import is_ip_blocked, validate_url


class _SilentMail(EmailService):
    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        return None


@pytest.fixture()
def auth_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthService:
    monkeypatch.setenv("AUTH_STORE_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("AUTH_LEGAL_DIR", str(tmp_path / "legal"))
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    store = AuthStore(tmp_path / "auth.json")
    service = AuthService(
        store,
        _SilentMail(),
        bootstrap_first_owner=True,
        single_user=False,
        skip_email_verification=True,
    )
    yield service
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()


def test_passkey_login_is_disabled(auth_service: AuthService):
    with pytest.raises(PasskeyError, match="disabled"):
        auth_service.passkey_login_options()
    with pytest.raises(PasskeyError, match="disabled"):
        auth_service.passkey_login_verify(
            credential_id="cred",
            client_data_json="eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdlIjoiYWJjIn0",
        )
    providers = auth_service.list_login_providers()
    assert providers["passkey"]["enabled"] is False


def test_oauth_does_not_auto_link_by_email(auth_service: AuthService):
    now = utcnow()
    auth_service._store.save_user(
        UserRecord(
            id="u1",
            first_name="Ada",
            last_name="Lovelace",
            username="ada",
            email="ada@nexa.test",
            password_hash=hash_password("Secret123"),
            email_verified=True,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    profile = OAuthProfile(
        provider="google",
        subject="google-sub-1",
        email="ada@nexa.test",
        email_verified=True,
        first_name="Ada",
        last_name="Google",
        username_hint="ada",
    )
    with pytest.raises(ValidationAuthError, match="already exists"):
        auth_service._login_with_oauth_profile(profile, user_agent=None, ip_address=None)


def test_password_reset_revokes_sessions(auth_service: AuthService):
    auth_service.register(
        first_name="Ada",
        last_name="Lovelace",
        username="ada",
        email="ada@nexa.test",
        password="Secret123",
        confirm_password="Secret123",
        accept_terms=True,
        accept_privacy=True,
        accept_license=True,
    )
    login = auth_service.login(email="ada@nexa.test", password="Secret123")
    token = login["session_token"]
    assert auth_service.get_user_for_token(token).email == "ada@nexa.test"

    user = auth_service._store.get_user_by_email("ada@nexa.test")
    assert user is not None
    code = "123456"
    auth_service._store.save_verification(
        EmailVerificationRecord(
            id="vr1",
            user_id=user.id,
            email=user.email,
            code_hash=hash_code(code),
            purpose="password_reset",
            expires_at=utcnow() + timedelta(minutes=15),
        )
    )
    auth_service.reset_password(
        email="ada@nexa.test",
        code=code,
        password="NewSecret1",
        confirm_password="NewSecret1",
    )
    with pytest.raises((UnauthorizedError, SessionInvalidError)):
        auth_service.get_user_for_token(token)


def test_ipv4_mapped_loopback_is_blocked():
    assert is_ip_blocked("::ffff:127.0.0.1") is True
    assert is_ip_blocked("::ffff:169.254.169.254") is True
    with pytest.raises(SSRFProtectionError):
        validate_url("http://[::ffff:127.0.0.1]/")


def test_github_owner_repo_rejects_path_traversal():
    with pytest.raises(PluginValidationError):
        _safe_owner_repo("..", "gists")
    with pytest.raises(PluginValidationError):
        _safe_owner_repo("owner/extra", "repo")
    assert _safe_owner_repo("octocat", "Hello-World") == ("octocat", "Hello-World")


def test_secret_patterns_cover_stripe_and_jwt():
    assert contains_secret("sk_live_abc1234567890")
    assert contains_secret("whsec_abc1234567890")
    assert contains_secret(
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )


def test_clear_memory_requires_authentication():
    client = TestClient(app)
    response = client.delete("/api/v1/memory")
    assert response.status_code == 401


def test_plugins_require_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLUGIN_STORE_PATH", str(tmp_path / "plugins.json"))
    monkeypatch.setenv("PLUGIN_KEY_PATH", str(tmp_path / "plugin.key"))
    monkeypatch.setenv("PLUGIN_WORKSPACE_DIR", str(tmp_path / "ws"))
    get_settings.cache_clear()
    get_plugin_manager.cache_clear()
    get_default_tool_registry.cache_clear()
    client = TestClient(app)
    assert client.get("/api/v1/plugins").status_code == 401
    invoke = client.post(
        "/api/v1/plugins/godot/invoke",
        json={"action": "run", "params": {}, "confirm": True},
    )
    assert invoke.status_code == 401
    get_plugin_manager.cache_clear()
    get_default_tool_registry.cache_clear()


def test_plugins_ok_with_bearer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_service: AuthService):
    monkeypatch.setenv("PLUGIN_STORE_PATH", str(tmp_path / "plugins.json"))
    monkeypatch.setenv("PLUGIN_KEY_PATH", str(tmp_path / "plugin.key"))
    monkeypatch.setenv("PLUGIN_WORKSPACE_DIR", str(tmp_path / "ws"))
    get_settings.cache_clear()
    get_plugin_manager.cache_clear()
    get_default_tool_registry.cache_clear()

    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_auth_store] = lambda: auth_service._store
    try:
        client = TestClient(app)
        auth_service.register(
            first_name="Ada",
            last_name="Lovelace",
            username="ada",
            email="ada@nexa.test",
            password="Secret123",
            confirm_password="Secret123",
            accept_terms=True,
            accept_privacy=True,
            accept_license=True,
        )
        login = auth_service.login(email="ada@nexa.test", password="Secret123")
        token = login["session_token"]
        listed = client.get(
            "/api/v1/plugins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200, listed.text
        assert any(p["id"] == "vscode" for p in listed.json()["plugins"])
        conn = client.post(
            "/api/v1/plugins/vscode/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={"permissions": ["files.read"]},
        )
        assert conn.status_code == 200, conn.text
    finally:
        app.dependency_overrides.clear()
        get_plugin_manager.cache_clear()
        get_default_tool_registry.cache_clear()


def test_non_global_special_use_addresses_are_blocked():
    assert is_ip_blocked("100.64.0.1") is True  # shared address space
    assert is_ip_blocked("192.0.2.10") is True  # documentation range
