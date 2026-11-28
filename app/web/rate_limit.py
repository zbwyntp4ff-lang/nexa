"""API-wide sliding-window rate limiter (in-process; use edge limits in production)."""
from __future__ import annotations

import threading
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SlidingWindow:
    def __init__(
        self,
        *,
        max_calls: int,
        window_seconds: float,
        max_keys: int = 10_000,
        prune_interval_seconds: float = 30.0,
    ) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._max_keys = max(1, max_keys)
        self._prune_interval = max(0.0, prune_interval_seconds)
        self._last_prune = 0.0
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune_expired(self, now: float) -> None:
        """Drop inactive keys so one-off clients cannot grow state forever."""
        expired = [
            key
            for key, timestamps in self._hits.items()
            if not timestamps or (now - timestamps[-1]) > self._window
        ]
        for key in expired:
            del self._hits[key]
        self._last_prune = now

    def allow(self, key: str, *, max_calls: int | None = None) -> bool:
        limit = self._max if max_calls is None else max_calls
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            should_prune = (now - self._last_prune) >= self._prune_interval
            # A full table forces cleanup before considering a new key, even
            # when the periodic sweep interval has not elapsed.
            if should_prune or (q is None and len(self._hits) >= self._max_keys):
                self._prune_expired(now)
                q = self._hits.get(key)

            # Bound memory under high-cardinality client-address traffic.
            # Existing clients continue to be rate-limited; new keys fail
            # closed until expired entries are reclaimed.
            if q is None:
                if len(self._hits) >= self._max_keys:
                    return False
                q = deque()
                self._hits[key] = q

            while q and (now - q[0]) > self._window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
            self._last_prune = 0.0


# Shared limiter so tests can reset hits without rebuilding the ASGI stack.
_api_limiter = SlidingWindow(max_calls=120, window_seconds=60.0)


def reset_api_rate_limiter() -> None:
    """Test helper — clears in-process API rate-limit state."""
    _api_limiter.clear()


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    """Limit ``/api/*`` by client IP. Skips ``/health``.

    Cap is read from settings on each request so ``API_RATE_LIMIT_PER_MINUTE=0``
    in tests disables limiting without restarting the app.
    """

    def __init__(self, app, *, max_calls: int = 120, window_seconds: float = 60.0) -> None:
        super().__init__(app)
        self._default_max = max_calls
        self._window = window_seconds

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.config.settings import get_settings

        max_calls = get_settings().api_rate_limit_per_minute
        if max_calls <= 0:
            return await call_next(request)
        path = request.url.path
        if path == "/health" or not path.startswith("/api/"):
            return await call_next(request)
        # Only trust the ASGI client address. Forwarded headers are attacker-
        # controlled unless a trusted proxy has already normalized request.client.
        key = request.client.host if request.client else "unknown"
        if not _api_limiter.allow(key, max_calls=max_calls):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit",
                    "message": "Too many requests. Please wait and try again.",
                },
            )
        return await call_next(request)
