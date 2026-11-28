"""In-process rate limits for authentication endpoints (Part 15)."""
from __future__ import annotations

import threading
import time
from collections import deque

from app.auth.errors import AuthError


class AuthRateLimitedError(AuthError):
    default_message = "Too many attempts. Please wait and try again."
    code = "AuthRateLimited"


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        max_calls: int,
        window_seconds: float,
        max_keys: int = 10_000,
        prune_interval_seconds: float = 60.0,
    ) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._max_keys = max(1, max_keys)
        self._prune_interval = max(1.0, prune_interval_seconds)
        self._hits: dict[str, deque[float]] = {}
        self._last_prune = 0.0
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self._window
        for key, hits in list(self._hits.items()):
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if not hits:
                self._hits.pop(key, None)
        self._last_prune = now

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_prune >= self._prune_interval:
                self._prune(now)

            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= self._max_keys:
                    self._prune(now)
                # Fail closed instead of allowing attacker-controlled IP
                # cardinality to grow process memory without a bound.
                if len(self._hits) >= self._max_keys:
                    raise AuthRateLimitedError()
                hits = deque()
                self._hits[key] = hits

            while hits and (now - hits[0]) > self._window:
                hits.popleft()
            if len(hits) >= self._max:
                raise AuthRateLimitedError()
            hits.append(now)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
            self._last_prune = 0.0

    def configure(self, *, max_calls: int, window_seconds: float) -> None:
        with self._lock:
            self._max = max_calls
            self._window = window_seconds
            self._hits.clear()
            self._last_prune = 0.0


# Support a 100-user shared-NAT login burst; per-account throttling remains 10/minute.
login_ip_limiter = SlidingWindowRateLimiter(max_calls=150, window_seconds=60.0)
login_account_limiter = SlidingWindowRateLimiter(max_calls=10, window_seconds=60.0)
# Allow a 100-user launch burst from a shared NAT while retaining an hourly abuse guard.
register_ip_limiter = SlidingWindowRateLimiter(max_calls=150, window_seconds=3600.0)


def reset_auth_rate_limiters() -> None:
    """Test helper — clears in-process auth rate-limit state."""
    login_ip_limiter.clear()
    login_account_limiter.clear()
    register_ip_limiter.clear()
