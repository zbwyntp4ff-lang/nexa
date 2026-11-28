from __future__ import annotations

from app.web import rate_limit


def test_sliding_window_bounds_number_of_client_keys(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    limiter = rate_limit.SlidingWindow(
        max_calls=2,
        window_seconds=60.0,
        max_keys=2,
        prune_interval_seconds=30.0,
    )

    assert limiter.allow("client-a")
    assert limiter.allow("client-b")
    assert not limiter.allow("client-c")
    # Existing clients remain usable even when the key table is full.
    assert limiter.allow("client-a")
    assert len(limiter._hits) == 2


def test_sliding_window_reclaims_expired_keys_when_capacity_is_reached(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    limiter = rate_limit.SlidingWindow(
        max_calls=2,
        window_seconds=10.0,
        max_keys=2,
        prune_interval_seconds=30.0,
    )

    assert limiter.allow("client-a")
    assert limiter.allow("client-b")
    clock[0] = 111.0

    # A full table triggers a cleanup even before the periodic sweep interval.
    assert limiter.allow("client-c")
    assert set(limiter._hits) == {"client-c"}
    assert len(limiter._hits) <= 2


def test_sliding_window_periodically_reclaims_inactive_keys(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    limiter = rate_limit.SlidingWindow(
        max_calls=2,
        window_seconds=10.0,
        max_keys=10,
        prune_interval_seconds=5.0,
    )

    assert limiter.allow("one-off-client")
    clock[0] = 116.0
    assert limiter.allow("active-client")
    assert set(limiter._hits) == {"active-client"}
