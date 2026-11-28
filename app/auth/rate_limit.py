"""In-process rate limits for authentication endpoints (Part 15)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.auth.errors import AuthError


class AuthRateLimitedError(AuthError):
    default_message = "Too many attempts. Please wait and try again."
    code = "AuthRateLimited"


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
                raise AuthRateLimitedError()
            q.append(now)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()

    def configure(self, *, max_calls: int, window_seconds: float) -> None:
        with self._lock:
            self._max = max_calls
            self._window = window_seconds
            self._hits.clear()


# 20 password attempts per IP per minute; 10 per account key.
login_ip_limiter = SlidingWindowRateLimiter(max_calls=20, window_seconds=60.0)
login_account_limiter = SlidingWindowRateLimiter(max_calls=10, window_seconds=60.0)
# Allow a 100-user launch burst from a shared NAT while retaining an hourly abuse guard.
register_ip_limiter = SlidingWindowRateLimiter(max_calls=150, window_seconds=3600.0)


def reset_auth_rate_limiters() -> None:
    """Test helper — clears in-process auth rate-limit state."""
    login_ip_limiter.clear()
    login_account_limiter.clear()
    register_ip_limiter.clear()
