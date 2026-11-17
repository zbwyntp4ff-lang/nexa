"""Persistent IP-based quotas for anonymous public-beta chat sessions.

The browser never receives provider credentials. Quotas are enforced in the
API process against the shared SQL database, so clearing browser storage does
not reset usage. IP addresses are SHA-256 hashed before storage.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.db.engine import get_database

DAILY_LIMIT = 15
HOURLY_LIMIT = 5


def _client_key(request: Request) -> str:
    # Use the transport peer, not user-supplied X-Forwarded-For. Configure
    # trusted proxy handling at the ASGI server if deployed behind a proxy.
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8")).hexdigest()


def consume_guest_request(request: Request) -> dict[str, int | str]:
    """Atomically consume one guest chat request or raise HTTP 429."""
    now = time.time()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = _client_key(request)
    db = get_database()
    row = db.fetchone(
        """
        INSERT INTO guest_usage (
            client_key, day_key, daily_count, hour_window_start, hour_count, updated_at
        ) VALUES (?, ?, 1, ?, 1, ?)
        ON CONFLICT(client_key) DO UPDATE SET
            day_key = excluded.day_key,
            daily_count = CASE
                WHEN guest_usage.day_key != excluded.day_key THEN 1
                ELSE guest_usage.daily_count + 1
            END,
            hour_count = CASE
                WHEN guest_usage.hour_window_start <= excluded.hour_window_start - 3600
                    THEN 1
                ELSE guest_usage.hour_count + 1
            END,
            hour_window_start = CASE
                WHEN guest_usage.hour_window_start <= excluded.hour_window_start - 3600
                    THEN excluded.hour_window_start
                ELSE guest_usage.hour_window_start
            END,
            updated_at = excluded.updated_at
        WHERE
            (guest_usage.day_key != excluded.day_key OR guest_usage.daily_count < ?)
            AND
            (guest_usage.hour_window_start <= excluded.hour_window_start - 3600
                OR guest_usage.hour_count < ?)
        RETURNING daily_count, hour_count, hour_window_start
        """,
        (key, day, now, now, DAILY_LIMIT, HOURLY_LIMIT),
    )
    if row is None:
        current = db.fetchone(
            "SELECT day_key, daily_count, hour_count, hour_window_start "
            "FROM guest_usage WHERE client_key = ?",
            (key,),
        )
        if current is None:
            raise HTTPException(status_code=429, detail={
                "error": "beta_limit_reached",
                "message": "Бесплатный лимит временно исчерпан. Попробуйте позже.",
            })
        daily_blocked = current[0] == day and current[1] >= DAILY_LIMIT
        retry_after = (
            max(1, int(86400 - (now % 86400))) if daily_blocked
            else max(1, int(current[3] + 3600 - now))
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "beta_limit_reached",
                "message": "Лимит HEXA Beta исчерпан. Попробуйте позже.",
                "daily_limit": DAILY_LIMIT,
                "hourly_limit": HOURLY_LIMIT,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    return {
        "daily_used": int(row[0]),
        "daily_limit": DAILY_LIMIT,
        "hourly_used": int(row[1]),
        "hourly_limit": HOURLY_LIMIT,
    }
