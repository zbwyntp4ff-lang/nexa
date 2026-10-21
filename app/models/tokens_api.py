"""Request/response models for the tokens HTTP API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TokenCostsPublic(BaseModel):
    chat: int
    agent: int
    image: int
    default: int


class UsageByReasonPublic(BaseModel):
    reason: str
    spent: int
    count: int


class TokenBalanceResponse(BaseModel):
    user_id: str
    balance: int
    daily_limit: int
    monthly_limit: int
    daily_spent: int
    monthly_spent: int
    daily_period: str
    monthly_period: str
    updated_at: datetime
    # NEXA internal credits — not OpenAI/Anthropic account balances.
    unit: str = "nexa_credits"
    costs: TokenCostsPublic | None = None
    usage_by_reason: list[UsageByReasonPublic] = Field(default_factory=list)


class LedgerEntryPublic(BaseModel):
    id: str
    user_id: str
    amount: int
    kind: str
    reason: str
    balance_before: int
    balance_after: int
    request_id: str | None = None
    actor_id: str | None = None
    created_at: datetime


class TokenHistoryResponse(BaseModel):
    items: list[LedgerEntryPublic]
    limit: int
    offset: int


class AdminAmountRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    amount: int = Field(..., gt=0)
    reason: str = Field(default="admin_adjustment", max_length=500)


class AdminLimitsRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    daily_limit: int | None = Field(default=None, ge=0)
    monthly_limit: int | None = Field(default=None, ge=0)
