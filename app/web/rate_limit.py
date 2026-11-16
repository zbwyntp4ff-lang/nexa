"""API-wide sliding-window rate limiter (in-process; use edge limits in production)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SlidingWindow:
    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, max_calls: int | None = None) -> bool:
        limit = self._max if max_calls is None else max_calls
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and (now - q[0]) > self._window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


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
