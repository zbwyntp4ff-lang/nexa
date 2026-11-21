"""Anonymous public-beta quota tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.beta.guest_quota import consume_guest_request
from app.db.engine import Database


class _Request:
    client = SimpleNamespace(host="203.0.113.8")
    cookies = {}


def test_guest_quota_allows_five_per_hour_and_blocks_sixth(tmp_path, monkeypatch):
    from app.beta import guest_quota

    db = Database(f"sqlite:///{tmp_path / 'beta.sqlite3'}")
    db.execute("""
        CREATE TABLE IF NOT EXISTS guest_usage (
            client_key TEXT PRIMARY KEY,
            day_key TEXT NOT NULL,
            daily_count INTEGER NOT NULL,
            hour_window_start REAL NOT NULL,
            hour_count INTEGER NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    monkeypatch.setattr(guest_quota, "get_database", lambda: db)
    for expected in range(1, 6):
        result = consume_guest_request(_Request())
        assert result["hourly_used"] == expected
    with pytest.raises(HTTPException) as exc:
        consume_guest_request(_Request())
    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "beta_limit_reached"


def test_guest_quota_hashes_client_ip(tmp_path, monkeypatch):
    from app.beta import guest_quota

    db = Database(f"sqlite:///{tmp_path / 'beta.sqlite3'}")
    db.execute("""
        CREATE TABLE IF NOT EXISTS guest_usage (
            client_key TEXT PRIMARY KEY,
            day_key TEXT NOT NULL,
            daily_count INTEGER NOT NULL,
            hour_window_start REAL NOT NULL,
            hour_count INTEGER NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    monkeypatch.setattr(guest_quota, "get_database", lambda: db)
    consume_guest_request(_Request())
    row = db.fetchone("SELECT client_key FROM guest_usage")
    assert row["client_key"] != "203.0.113.8"
    assert len(row["client_key"]) == 64


def test_public_beta_allows_guest_chat_even_when_tokens_are_enforced(monkeypatch):
    from app.api.routes import chat as chat_routes
    from app.config.settings import Settings

    consumed = []
    monkeypatch.setattr(chat_routes, "consume_guest_request", lambda request: consumed.append(request))
    request = _Request()
    monkeypatch.setenv("NEXA_PUBLIC_BETA", "true")
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    settings = Settings(_env_file=None)
    result = chat_routes.resolve_chat_user(request, None, None, settings)
    assert result is None
    assert consumed == [request]


def test_guest_chat_stays_closed_when_public_beta_is_disabled(monkeypatch):
    from app.api.routes import chat as chat_routes
    from app.auth.errors import UnauthorizedError
    from app.config.settings import Settings

    monkeypatch.setenv("NEXA_PUBLIC_BETA", "false")
    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    settings = Settings(_env_file=None)
    with pytest.raises(UnauthorizedError):
        chat_routes.resolve_chat_user(_Request(), None, None, settings)


def test_guest_quota_blocks_after_fifteen_daily_requests(tmp_path, monkeypatch):
    from app.beta import guest_quota

    db = Database(f"sqlite:///{tmp_path / 'daily-beta.sqlite3'}")
    monkeypatch.setattr(guest_quota, "get_database", lambda: db)
    monkeypatch.setattr(guest_quota, "HOURLY_LIMIT", 20)
    for expected in range(1, 16):
        result = consume_guest_request(_Request())
        assert result["daily_used"] == expected
    with pytest.raises(HTTPException) as exc:
        consume_guest_request(_Request())
    assert exc.value.status_code == 429
    assert exc.value.detail["daily_limit"] == 15


def test_public_beta_forces_default_text_chat(monkeypatch):
    from app.api.routes.chat import _apply_public_beta_restrictions
    from app.config.settings import Settings
    from app.models.chat import ChatRequest

    monkeypatch.setenv("NEXA_PUBLIC_BETA", "true")
    settings = Settings(_env_file=None)
    request = ChatRequest(
        message="hello",
        model="some-expensive-model",
        task="research",
        attachment_ids=["attachment-1"],
        use_knowledge_base=True,
        knowledge_project_id="project-1",
    )
    limited = _apply_public_beta_restrictions(request, None, settings)
    assert limited.model is None
    assert limited.task is None
    assert limited.attachment_ids == []
    assert limited.use_knowledge_base is False
    assert limited.knowledge_project_id is None


def test_public_beta_rejects_oversized_message(monkeypatch):
    from app.api.routes.chat import _apply_public_beta_restrictions
    from app.config.settings import Settings
    from app.models.chat import ChatRequest

    monkeypatch.setenv("NEXA_PUBLIC_BETA", "true")
    settings = Settings(_env_file=None)
    request = ChatRequest(message="x" * 3001)
    with pytest.raises(HTTPException) as exc:
        _apply_public_beta_restrictions(request, None, settings)
    assert exc.value.status_code == 413
    assert exc.value.detail["error"] == "beta_message_too_long"


def test_guest_quota_identifier_uses_secret_hmac_key(monkeypatch):
    from app.beta import guest_quota

    request = _Request()
    monkeypatch.setattr(guest_quota, "get_settings", lambda: SimpleNamespace(guest_quota_hash_key="first-secret-key-which-is-long-enough-123"))
    first = guest_quota._client_key(request)
    monkeypatch.setattr(guest_quota, "get_settings", lambda: SimpleNamespace(guest_quota_hash_key="second-secret-key-which-is-long-enough-456"))
    second = guest_quota._client_key(request)
    assert first != second
    assert len(first) == 64
    assert len(second) == 64
