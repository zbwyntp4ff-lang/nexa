"""Public beta status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.beta.guest_quota import get_guest_usage

router = APIRouter(prefix="/api/v1/beta", tags=["public-beta"])


@router.get("/usage")
def beta_usage(request: Request) -> dict[str, int]:
    """Return the current anonymous visitor's remaining chat allowance."""
    return get_guest_usage(request)
