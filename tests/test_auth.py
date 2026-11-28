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
    monkeypatch.setenv("AUTH_LEGAL_DIR", str(tmp_path / "legal"))
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


def test_providers_list_includes_device_and_passkey(auth_env):
    client, _, _ = auth_env
    response = client.get("/api/v1/auth/providers")
    assert response.status_code == 200
    data = response.json()
    assert data["device"]["enabled"] is True
    # Part 15: passkey login stays disabled until WebAuthn signatures are verified.
    assert data["passkey"]["enabled"] is False
    assert data["password"]["enabled"] is True
    assert {p["id"] for p in data["oauth"]} == {"google", "github", "apple"}


def test_device_login_approve_and_poll(auth_env):
    client, mail, _ = auth_env
    _register(client)
    code = mail.last_code()
    client.post("/api/v1/auth/verify-email", json={"email": "ada@nexa.test", "code": code})
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@nexa.test", "password": "Secret123"},
    )
    assert login.status_code == 200

    started = client.post("/api/v1/auth/device/start")
    assert started.status_code == 200
    body = started.json()
    device_code = body["device_code"]
    user_code = body["user_code"]

    pending = client.post("/api/v1/auth/device/poll", json={"device_code": device_code})
    assert pending.status_code == 428

    approved = client.post("/api/v1/auth/device/approve", json={"user_code": user_code})
    assert approved.status_code == 200, approved.text

    # New client simulates the waiting desktop session
    desktop = TestClient(app)
    polled = desktop.post("/api/v1/auth/device/poll", json={"device_code": device_code})
    assert polled.status_code == 200, polled.text
    assert polled.json()["user"]["email"] == "ada@nexa.test"
    assert "session_token" not in polled.json()
    assert "nexa_session" in polled.cookies
    me = desktop.get("/api/v1/auth/me")
    assert me.status_code == 200


def test_device_password_login_approves(auth_env):
    client, mail, _ = auth_env
    _register(client)
    code = mail.last_code()
    client.post("/api/v1/auth/verify-email", json={"email": "ada@nexa.test", "code": code})
    started = client.post("/api/v1/auth/device/start")
    body = started.json()
    phone = TestClient(app)
    approved = phone.post(
        "/api/v1/auth/device/login",
        json={
            "email": "ada@nexa.test",
            "password": "Secret123",
            "user_code": body["user_code"],
        },
    )
    assert approved.status_code == 200, approved.text
    desktop = TestClient(app)
    polled = desktop.post("/api/v1/auth/device/poll", json={"device_code": body["device_code"]})
    assert polled.status_code == 200
    assert polled.json()["user"]["email"] == "ada@nexa.test"
    assert "session_token" not in polled.json()
    assert "nexa_session" in polled.cookies


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
    assert "session_token" not in login.json()

    client.post("/api/v1/auth/logout")
    login_username = client.post(
        "/api/v1/auth/login",
        json={"email": "ada", "password": "Secret123"},
    )
    assert login_username.status_code == 200
    assert login_username.json()["user"]["username"] == "ada"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "ada"
    assert me.json()["user"]["is_owner"] is True

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_slides_on_activity_until_logout(auth_env):
    """Active use renews expiry; logout still invalidates the session."""
    from datetime import timedelta

    from app.auth.models import utcnow

    client, mail, service = auth_env
    _register(client)
    client.post(
        "/api/v1/auth/verify-email",
        json={"email": "ada@nexa.test", "code": mail.last_code()},
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "ada@nexa.test", "password": "Secret123"},
        ).status_code
        == 200
    )
    session = next(s for s in service._store._sessions.values() if s.revoked_at is None)
    # Less than half of the 3600s test TTL → touch should renew.
    near = utcnow() + timedelta(minutes=10)
    session.expires_at = near
    service._store.save_session(session)

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    refreshed = service._store.get_session(session.id)
    assert refreshed is not None
    assert refreshed.expires_at > near
    assert "nexa_session" in me.cookies

    assert client.post("/api/v1/auth/logout").status_code == 200
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
    assert "session_token" not in body

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


def test_device_start_includes_origin_and_qr(auth_env):
    client, _, _ = auth_env
    started = client.post(
        "/api/v1/auth/device/start",
        json={"origin": "http://localhost:4820"},
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["verification_uri_complete"].startswith("http://localhost:4820/auth/device?code=")
    assert "qr_payload" in body
    assert "qr_svg" in body
    assert "/auth/device?code=" in body["qr_payload"]
    page = client.get("/auth/device", params={"code": "ABC-DEF"})
    assert page.status_code == 200
    assert "Подтверждение NEXA" in page.text


def test_legal_documents_endpoint(auth_env):
    client, _, _ = auth_env
    listing = client.get("/api/v1/auth/legal")
    assert listing.status_code == 200
    ids = {row["id"] for row in listing.json()["documents"]}
    assert ids == {"terms_of_service", "privacy_policy", "license_agreement"}
    assert listing.json()["holder"]["name"]
    license_doc = client.get("/api/v1/auth/legal/license_agreement")
    assert license_doc.status_code == 200
    assert "NEXA" in license_doc.json()["body"]
    assert "Правообладатель" in license_doc.json()["body"]


def test_legal_holder_uses_owner_and_can_be_updated(auth_env):
    client, mail, _ = auth_env
    listing = client.get("/api/v1/auth/legal")
    assert listing.json()["holder"]["kind"] == "individual"
    _register(client)
    client.post(
        "/api/v1/auth/verify-email",
        json={"email": "ada@nexa.test", "code": mail.last_code()},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@nexa.test", "password": "Secret123"},
    )
    assert login.status_code == 200
    named = client.get("/api/v1/auth/legal")
    assert named.json()["holder"]["name"] == "Ada Lovelace"
    assert named.json()["holder"]["contact"] == "ada@nexa.test"
    license_doc = client.get("/api/v1/auth/legal/license_agreement")
    assert "Ada Lovelace" in license_doc.json()["body"]
    saved = client.put(
        "/api/v1/auth/legal/holder",
        json={
            "name": "ООО Некса",
            "kind": "company",
            "contact": "legal@nexa.test",
            "inn": "7700000000",
            "country": "RU",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["holder"]["kind"] == "company"
    assert saved.json()["holder"]["inn"] == "7700000000"
    updated = client.get("/api/v1/auth/legal/license_agreement")
    assert "ООО Некса" in updated.json()["body"]
    assert "юридическое лицо" in updated.json()["body"]


def test_google_oauth_file_enables_provider(tmp_path, monkeypatch):
    from app.auth.credentials import save_google_oauth
    from app.auth.oauth import list_provider_status
    from app.config.settings import Settings

    folder = tmp_path / "oauth"
    settings = Settings.model_construct(
        oauth_google_client_id=None,
        oauth_google_client_secret=None,
        oauth_github_client_id=None,
        oauth_github_client_secret=None,
        oauth_apple_client_id=None,
        oauth_apple_client_secret=None,
        oauth_credentials_dir=str(folder),
    )
    save_google_oauth(settings, "google-client-id.apps.googleusercontent.com", "google-secret-value")
    status = {row["id"]: row["enabled"] for row in list_provider_status(settings)}
    assert status["google"] is True
    assert status["github"] is False



def test_oauth_email_verified_string_false_is_not_trusted():
    from app.auth.oauth import _as_bool

    assert _as_bool("false", default=True) is False
    assert _as_bool("0", default=True) is False
    assert _as_bool("true") is True
    assert _as_bool(True) is True


def test_corrupt_auth_store_fails_closed(tmp_path: Path):
    """A corrupt account database must not silently become an empty account list."""
    store_path = tmp_path / "auth.json"
    store_path.write_text('{"users": [', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Cannot load NEXA auth store"):
        AuthStore(store_path)


def test_missing_auth_store_starts_empty(tmp_path: Path):
    """A genuinely new install still starts with an empty account database."""
    store = AuthStore(tmp_path / "new-auth.json")
    assert store.list_users() == []


def test_ipconfig_output_uses_portable_text_encoding(monkeypatch):
    import subprocess
    from app.auth.service import _ipv4s_from_ipconfig

    def fake_check_output(command, **kwargs):
        assert command == ["ipconfig"]
        assert kwargs["encoding"] == "utf-8"
        return "IPv4 Address. . . . . . . . . . . : 192.168.1.25"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    assert _ipv4s_from_ipconfig() == ["192.168.1.25"]

def test_oauth_missing_email_verified_claim_is_unverified():
    from app.auth.oauth import _as_bool

    assert _as_bool(None, default=False) is False

def test_device_session_token_is_not_persisted_to_auth_store(tmp_path: Path):
    from datetime import timedelta
    from app.auth.models import DeviceLoginRecord, utcnow

    store_path = tmp_path / "auth.json"
    store = AuthStore(store_path)
    secret_token = "device-session-token-must-stay-in-memory"
    store.save_device(
        DeviceLoginRecord(
            device_code="device-code",
            user_code="ABCD-EFGH",
            status="approved",
            user_id="user-1",
            session_token=secret_token,
            expires_at=utcnow() + timedelta(minutes=5),
        )
    )
    assert secret_token not in store_path.read_text(encoding="utf-8")
    reloaded = AuthStore(store_path)
    assert reloaded.get_device("device-code").session_token is None


def test_delete_user_removes_device_and_passkey_challenges(tmp_path: Path):
    from datetime import timedelta
    from app.auth.models import (
        DeviceLoginRecord,
        PasskeyChallengeRecord,
        UserRecord,
        utcnow,
    )

    store = AuthStore(tmp_path / "auth.json")
    user = UserRecord(
        id="user-1", first_name="Test", last_name="User", username="test_user",
        email="test@example.com", password_hash="unused",
    )
    store.save_user(user)
    expiry = utcnow() + timedelta(minutes=5)
    store.save_device(DeviceLoginRecord(
        device_code="device-1", user_code="AAAA-BBBB", user_id="user-1", expires_at=expiry
    ))
    store.save_passkey_challenge(PasskeyChallengeRecord(
        challenge="challenge-1", user_id="user-1", expires_at=expiry
    ))

    assert store.delete_user("user-1") is True
    assert store.get_device("device-1") is None
    assert "challenge-1" not in store._passkey_challenges

def test_auth_store_migrates_legacy_plaintext_device_tokens(tmp_path: Path):
    import json

    store_path = tmp_path / "auth.json"
    raw = {
        "users": [], "verifications": [], "sessions": [],
        "devices": [{
            "device_code": "legacy-device-code",
            "user_code": "ABCD-EFGH",
            "status": "approved",
            "user_id": "user-1",
            "session_token": "legacy-plaintext-bearer-token",
            "created_at": "2026-11-19T10:00:00+00:00",
            "expires_at": "2026-11-19T10:05:00+00:00",
        }],
        "oauth_states": [], "passkey_challenges": [],
    }
    store_path.write_text(json.dumps(raw), encoding="utf-8")
    store = AuthStore(store_path)

    persisted = store_path.read_text(encoding="utf-8")
    assert "legacy-plaintext-bearer-token" not in persisted
    assert store.get_device("legacy-device-code") is None

def test_auth_store_email_repair_preserves_sessions_and_pending_devices(tmp_path: Path):
    import json
    from datetime import timedelta
    from app.auth.models import DeviceLoginRecord, SessionRecord, UserRecord, utcnow

    store_path = tmp_path / "auth.json"
    user = UserRecord(
        id="user-1", first_name="Test", last_name="User", username="test_user",
        email="•test@example.com", password_hash="unused",
    )
    expiry = utcnow() + timedelta(minutes=5)
    raw = {
        "users": [user.model_dump(mode="json")],
        "verifications": [],
        "sessions": [SessionRecord(
            id="session-1", user_id="user-1", token_hash="hashed-token", expires_at=expiry
        ).model_dump(mode="json")],
        "devices": [DeviceLoginRecord(
            device_code="pending-device", user_code="AAAA-BBBB", expires_at=expiry
        ).model_dump(mode="json")],
        "oauth_states": [], "passkey_challenges": [],
    }
    store_path.write_text(json.dumps(raw), encoding="utf-8")

    store = AuthStore(store_path)
    assert store.get_user("user-1").email == "test@example.com"
    assert store.get_session("session-1") is not None
    assert store.get_device("pending-device") is not None



def test_auth_store_atomically_rejects_duplicate_email_and_username(tmp_path: Path):
    from app.auth.models import UserRecord, utcnow
    from app.auth.passwords import hash_password

    store = AuthStore(tmp_path / "auth.json")
    now = utcnow()

    def user(user_id: str, email: str, username: str) -> UserRecord:
        return UserRecord(
            id=user_id, first_name="Test", last_name="User", username=username,
            email=email, password_hash=hash_password("Secret123"),
            email_verified=True, is_active=True, created_at=now, updated_at=now,
        )

    assert store.create_user_if_available(user("u1", "same@example.test", "first")) is None
    assert store.create_user_if_available(user("u2", "same@example.test", "second")) == "email"
    assert store.create_user_if_available(user("u3", "other@example.test", "first")) == "username"
    assert [u.id for u in store.list_users()] == ["u1"]


def test_auth_store_enforces_single_user_inside_atomic_insert(tmp_path: Path):
    from app.auth.models import UserRecord, utcnow
    from app.auth.passwords import hash_password

    store = AuthStore(tmp_path / "auth.json")
    now = utcnow()

    def user(user_id: str) -> UserRecord:
        return UserRecord(
            id=user_id, first_name="Test", last_name="User",
            username=f"user_{user_id}", email=f"{user_id}@example.test",
            password_hash=hash_password("Secret123"), email_verified=True,
            is_active=True, created_at=now, updated_at=now,
        )

    assert store.create_user_if_available(user("u1"), single_user=True) is None
    assert store.create_user_if_available(user("u2"), single_user=True) == "registration_closed"
    assert [u.id for u in store.list_users()] == ["u1"]


def test_one_hundred_distinct_users_can_register_concurrently(auth_env):
    """A shared-IP launch burst must not serialize the event loop or hit the old 10/hour cap."""
    from concurrent.futures import ThreadPoolExecutor

    client, _, service = auth_env

    def register(index: int):
        return client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Load",
                "last_name": "Test",
                "username": f"loaduser{index}",
                "email": f"loaduser{index}@nexa.test",
                "password": "Secret123",
                "confirm_password": "Secret123",
                "accept_terms": True,
                "accept_privacy": True,
                "accept_license": True,
            },
        )

    with ThreadPoolExecutor(max_workers=100) as pool:
        responses = list(pool.map(register, range(100)))

    assert all(response.status_code == 201 for response in responses), [
        (response.status_code, response.text) for response in responses
        if response.status_code != 201
    ]
    assert len(service._store.list_users()) == 100
    assert len({user.email for user in service._store.list_users()}) == 100
    assert len({user.username for user in service._store.list_users()}) == 100
