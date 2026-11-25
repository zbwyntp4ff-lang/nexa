"""Helpers to enforce token charges around AI route handlers."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from app.tokens.service import TokenService

T = TypeVar("T")


def resolve_request_id(*candidates: str | None) -> str:
    for value in candidates:
        if value and value.strip():
            return value.strip()
    return str(uuid.uuid4())


async def run_with_token_charge(
    tokens: TokenService,
    *,
    user_id: str,
    amount: int,
    request_id: str,
    reason: str,
    work: Callable[[], Awaitable[T]],
) -> T:
    """Charge → run async work → refund on any exception."""
    tokens.charge(user_id, amount, request_id=request_id, reason=reason)
    try:
        return await work()
    except Exception:
        tokens.refund(request_id, user_id=user_id, reason="ai_error_refund")
        raise


async def stream_with_token_charge(
    tokens: TokenService,
    *,
    user_id: str,
    amount: int,
    request_id: str,
    reason: str,
    events: AsyncIterator[str],
) -> AsyncIterator[str]:
    """Charge before streaming; refund if the generator raises."""
    tokens.charge(user_id, amount, request_id=request_id, reason=reason)
    try:
        async for item in events:
            yield item
    except Exception:
        tokens.refund(request_id, reason="ai_error_refund")
        raise
