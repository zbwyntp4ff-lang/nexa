"""Auth flow: register → verify email → login → session cookie."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_auth_store
from app.auth.email import EmailService
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.config.settings import get_settings
from app.main import app


class CapturingEmail(EmailService):
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        self.messages.append((to, subject, text_body))

    def last_code(self) -> str:
        body = self.messages[-1][2]
        match = re.search(r"\b(\d{6})\b", body)
        assert match, f"no code in email body: {body}"
        return match.group(1)


@pytest.fixture()
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store_path = tmp_path / "auth.json"
    monkeypatch.setenv("AUTH_STORE_PATH", str(store_path))
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()

    mail = CapturingEmail()
    store = AuthStore(store_path)
    service = AuthService(
        store,
        mail,
        code_ttl_seconds=900,
        resend_cooldown_seconds=60,
        max_verify_attempts=5,
        session_ttl_seconds=3600,
        app_name="NEXA Test",
        bootstrap_first_owner=True,
        single_user=False,
        skip_email_verification=False,
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_auth_store] = lambda: store
    client = TestClient(app)
    yield client, mail, service
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()


def _register(client: TestClient, email: str = "ada@nexa.test", username: str = "ada") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "username": username,
            "email": email,
            "password": "Secret123",
            "confirm_password": "Secret123",
            "accept_terms": True,
            "accept_privacy": True,
            "accept_license": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_requires_consents(auth_env):
    client, _, _ = auth_env
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "username": "ada",
            "email": "ada@nexa.test",
            "password": "Secret123",
            "confirm_password": "Secret123",
            "accept_terms": True,
            "accept_privacy": False,
            "accept_license": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ConsentRequired"


def test_full_auth_flow(auth_env):
    client, mail, _ = auth_env
    created = _register(client)
    assert created["user"]["email_verified"] is False
    assert created["user"]["is_active"] is False
    assert created["user"]["is_owner"] is False
    assert len(created["user"]["consents"]) == 3
    assert all(c["version"] for c in created["user"]["consents"])
    assert len(mail.messages) == 1
    code = mail.last_code()

    # Login before verify must fail
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@nexa.test", "password": "Secret123"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"] == "EmailNotVerified"

    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "ada@nexa.test", "code": code},
    )
    assert verified.status_code == 200
    assert verified.json()["user"]["email_verified"] is True
    assert verified.json()["user"]["is_active"] is True
    # First verified account becomes owner (Developer button).
    assert verified.json()["user"]["is_owner"] is True

    # Code is single-use
    reuse = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "ada@nexa.test", "code": code},
    )
    assert reuse.status_code == 400

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@nexa.test", "password": "Secret123"},
    )
    assert login.status_code == 200
    assert "nexa_session" in login.cookies
    assert login.json()["user"]["is_owner"] is True

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "ada"
    assert me.json()["user"]["is_owner"] is True

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_second_user_is_not_auto_owner(auth_env):
    client, mail, _ = auth_env
    _register(client, email="first@nexa.test", username="first")
    client.post(
        "/api/v1/auth/verify-email",
        json={"email": "first@nexa.test", "code": mail.last_code()},
    )
    _register(client, email="second@nexa.test", username="second")
    second = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "second@nexa.test", "code": mail.last_code()},
    )
    assert second.status_code == 200
    assert second.json()["user"]["is_owner"] is False


def test_single_user_owner_setup(tmp_path, monkeypatch):
    from app.api.deps import get_auth_service, get_auth_store
    from app.auth.email import EmailService
    from app.auth.service import AuthService
    from app.auth.store import AuthStore
    from app.config.settings import get_settings
    from app.main import app

    class CapturingEmail(EmailService):
        def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
            pass

    store_path = tmp_path / "auth-single.json"
    monkeypatch.setenv("AUTH_STORE_PATH", str(store_path))
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    store = AuthStore(store_path)
    service = AuthService(
        store,
        CapturingEmail(),
        single_user=True,
        skip_email_verification=True,
        bootstrap_first_owner=True,
    )
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_auth_store] = lambda: store
    client = TestClient(app)

    status = client.get("/api/v1/auth/status")
    assert status.json()["registration_open"] is True

    created = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Me",
            "last_name": "Owner",
            "username": "owner",
            "email": "me@nexa.test",
            "password": "Secret123",
            "confirm_password": "Secret123",
            "accept_terms": True,
            "accept_privacy": True,
            "accept_license": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["ready"] is True
    assert body["user"]["is_owner"] is True
    assert body["user"]["email_verified"] is True
    assert "nexa_session" in created.cookies

    blocked = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Other",
            "last_name": "User",
            "username": "other",
            "email": "other@nexa.test",
            "password": "Secret123",
            "confirm_password": "Secret123",
            "accept_terms": True,
            "accept_privacy": True,
            "accept_license": True,
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"] == "RegistrationClosed"

    assert client.get("/api/v1/auth/status").json()["registration_open"] is False
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()


def test_verification_attempt_limit(auth_env):
    client, mail, _ = auth_env
    _register(client, email="limit@nexa.test", username="limituser")
    for _ in range(5):
        bad = client.post(
            "/api/v1/auth/verify-email",
            json={"email": "limit@nexa.test", "code": "000000"},
        )
        assert bad.status_code in (400, 429)
    final = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "limit@nexa.test", "code": mail.last_code()},
    )
    assert final.status_code == 429
    assert final.json()["error"] == "VerificationAttemptsExceeded"


def test_password_not_stored_plaintext(auth_env):
    client, _, service = auth_env
    _register(client, email="hash@nexa.test", username="hashuser")
    user = service._store.get_user_by_email("hash@nexa.test")
    assert user is not None
    assert user.password_hash.startswith("scrypt$")
    assert "Secret123" not in user.password_hash
    records = service._store.list_verifications_for_user(user.id)
    assert records
    assert len(records[0].code_hash) == 64
    assert records[0].code_hash != "123456"
