"""Anonymous public-beta quota tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.beta.guest_quota import consume_guest_request
from app.db.engine import Database


class _Request:
    client = SimpleNamespace(host="203.0.113.8")


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
