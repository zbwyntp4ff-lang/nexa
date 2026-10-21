"""Persisted models for the internal AI token wallet."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


LedgerKind = Literal[
    "debit",
    "credit",
    "refund",
    "admin_credit",
    "admin_debit",
]

ChargeStatus = Literal["charged", "refunded"]


class TokenAccount(BaseModel):
    user_id: str
    balance: int = 0
    daily_limit: int = 1_000
    monthly_limit: int = 10_000
    daily_spent: int = 0
    daily_period: str = ""  # YYYY-MM-DD UTC
    monthly_spent: int = 0
    monthly_period: str = ""  # YYYY-MM UTC
    updated_at: datetime = Field(default_factory=utcnow)


class LedgerEntry(BaseModel):
    id: str
    user_id: str
    amount: int  # signed: negative = spend, positive = credit/refund
    kind: LedgerKind
    reason: str
    balance_before: int
    balance_after: int
    request_id: str | None = None
    actor_id: str | None = None  # admin or system
    created_at: datetime = Field(default_factory=utcnow)


class ChargeRecord(BaseModel):
    """Idempotency index for AI request charges."""

    request_id: str
    user_id: str
    amount: int
    status: ChargeStatus
    reason: str
    created_at: datetime = Field(default_factory=utcnow)
    refunded_at: datetime | None = None
