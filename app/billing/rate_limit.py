"""Simple in-process rate limiter for billing endpoints."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.billing.errors import RateLimitedError


class SlidingWindowRateLimiter:
    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and (now - q[0]) > self._window:
                q.popleft()
            if len(q) >= self._max:
                raise RateLimitedError()
            q.append(now)


# Conservative defaults: 20 checkout/portal actions per minute per user.
billing_action_limiter = SlidingWindowRateLimiter(max_calls=20, window_seconds=60.0)
webhook_ip_limiter = SlidingWindowRateLimiter(max_calls=120, window_seconds=60.0)
