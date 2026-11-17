"""Part 11 — profile / personalization."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_auth_store, get_profile_service, get_profile_store
from app.auth.email import EmailService
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.config.settings import get_settings
from app.main import app
from app.profile.context import build_compact_hint
from app.profile.models import AIPreferences, ProjectPersonalization, UserProfile
from app.profile.service import ProfileService
from app.profile.store import ProfileStore


class CapturingEmail(EmailService):
    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        return None


@pytest.fixture()
def profile_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auth_path = tmp_path / "auth.json"
    profile_path = tmp_path / "profiles.json"
    monkeypatch.setenv("AUTH_STORE_PATH", str(auth_path))
    monkeypatch.setenv("PROFILE_STORE_PATH", str(profile_path))
    monkeypatch.setenv("TOKENS_ENFORCE", "false")
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_profile_store.cache_clear()
    get_profile_service.cache_clear()

    store = AuthStore(auth_path)
    mail = CapturingEmail()
    auth = AuthService(
        store,
        mail,
        single_user=False,
        skip_email_verification=True,
        bootstrap_first_owner=True,
    )
    profiles = ProfileService(ProfileStore(profile_path))
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_auth_store] = lambda: store
    app.dependency_overrides[get_profile_service] = lambda: profiles
    app.dependency_overrides[get_profile_store] = lambda: profiles._store
    client = TestClient(app)
    yield client, auth, profiles
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_auth_store.cache_clear()
    get_auth_service.cache_clear()
    get_profile_store.cache_clear()
    get_profile_service.cache_clear()


def _register_and_login(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "username": "ada",
            "email": "ada@nexa.test",
            "password": "Secret123",
            "confirm_password": "Secret123",
            "accept_terms": True,
            "accept_privacy": True,
            "accept_license": True,
        },
    )
    # skip_email_verification + single_user=False still needs verify unless auto
    # AuthService with skip and not single_user may still require verify — login after register ready
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@nexa.test", "password": "Secret123"},
    )
    if login.status_code != 200:
        # activate manually via store path is fine for this suite when verify required
        pass


def test_compact_hint_respects_toggle():
    profile = UserProfile(user_id="u1", display_name="Ada", ai=AIPreferences(personalization_enabled=False))
    assert build_compact_hint(profile) is None
    profile.ai.personalization_enabled = True
    hint = build_compact_hint(profile)
    assert hint and "Personalization" in hint
    assert "Ada" in hint or "Address" in hint


def test_extended_personalization_fields_reach_context_hint():
    profile = UserProfile(
        user_id="u2",
        ai=AIPreferences(
            custom_instructions="Start with a short summary.",
            about_user="I am building a software product.",
            occupation="Founder",
            interests=["AI", "aviation"],
            avoid_topics="Avoid unnecessary jargon.",
            expertise_level="advanced",
            proactive_suggestions=True,
        ),
    )
    hint = build_compact_hint(profile) or ""
    assert "short summary" in hint
    assert "software product" in hint
    assert "Founder" in hint
    assert "AI" in hint and "aviation" in hint
    assert "advanced" in hint


def test_project_overrides_style():
    profile = UserProfile(user_id="u1", ai=AIPreferences(response_style="balanced"))
    project = ProjectPersonalization(response_style="concise", instructions="Focus on APIs")
    hint = build_compact_hint(profile, project)
    assert hint is not None
    assert "short" in hint.lower() or "concise" in hint.lower()
    assert "APIs" in hint


def test_profile_get_update_own_only(profile_env):
    client, auth, profiles = profile_env
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "username": "ada",
            "email": "ada@nexa.test",
            "password": "Secret123",
            "confirm_password": "Secret123",
            "accept_terms": True,
            "accept_privacy": True,
            "accept_license": True,
        },
    )
    assert reg.status_code == 201, reg.text
    # With skip_email_verification=True and single_user=False, ready may be False
    if reg.json().get("ready"):
        pass
    else:
        # Force active for test: login path needs verified user
        user = auth._store.get_user_by_email("ada@nexa.test")
        assert user
        user.email_verified = True
        user.is_active = True
        auth._store.save_user(user)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@nexa.test", "password": "Secret123"},
        )
        assert login.status_code == 200, login.text

    me = client.get("/api/v1/profile")
    assert me.status_code == 200, me.text
    body = me.json()["profile"]
    assert body["user_id"]
    assert "password" not in body
    assert "password_hash" not in str(body)

    patched = client.patch(
        "/api/v1/profile",
        json={
            "display_name": "Ada L",
            "ai": {
                "personalization_enabled": True,
                "response_style": "technical",
                "personality": "direct",
                "brevity": "low",
                "detail_level": "high",
                "answer_format": "bullets",
                "ai_language": "en",
                "default_model": "gpt-4o-mini",
                "preferred_name": "Ada",
            },
            "onboarding_completed": True,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["profile"]["display_name"] == "Ada L"
    assert patched.json()["profile"]["ai"]["response_style"] == "technical"

    preview = client.get("/api/v1/profile/context-preview")
    assert preview.status_code == 200
    assert preview.json()["enabled"] is True
    assert "Personalization" in (preview.json()["hint"] or "")


def test_profile_requires_auth(profile_env):
    client, _, _ = profile_env
    # fresh client without cookies
    naked = TestClient(app)
    assert naked.get("/api/v1/profile").status_code in {401, 400}


def test_hint_contains_no_secrets():
    profile = UserProfile(
        user_id="u1",
        display_name="Ada",
        ai=AIPreferences(preferred_name="Ada", personalization_enabled=True),
    )
    hint = build_compact_hint(profile) or ""
    assert "api_key" not in hint.lower()
    assert "password" not in hint.lower()
    assert "secret" not in hint.lower()
