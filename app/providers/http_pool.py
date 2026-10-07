"""Shared httpx client for local / Ollama providers.

Creating a new ``AsyncClient`` per chat request pays TCP+TLS setup before the
first token. One process-wide client keeps connections warm.
"""
from __future__ import annotations

import httpx

_client: httpx.AsyncClient | None = None


def get_http_client(timeout_seconds: float) -> httpx.AsyncClient:
    """Return a process-wide AsyncClient, recreating it if the timeout changes."""
    global _client
    timeout = httpx.Timeout(
        connect=5.0,
        read=timeout_seconds,
        write=30.0,
        pool=5.0,
    )
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            http2=False,
        )
    else:
        # Keep the same pool; per-request timeout is passed on stream/post calls.
        _client.timeout = timeout
    return _client
