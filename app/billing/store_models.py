"""Billing domain models persisted by :mod:`app.billing.store`."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.billing.plans import BillingInterval, PlanId


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


SubscriptionStatus = Literal[
    "active",
    "trialing",
    "past_due",
    "canceled",
    "incomplete",
    "incomplete_expired",
    "unpaid",
    "paused",
]
PaymentStatus = Literal["pending", "succeeded", "failed", "canceled", "refunded"]
InvoiceStatus = Literal["draft", "open", "paid", "void", "uncollectible"]


class SubscriptionRecord(BaseModel):
    id: str
    user_id: str
    plan: PlanId = "free"
    status: SubscriptionStatus = "active"
    billing_interval: BillingInterval = "month"
    provider: str = "stripe"
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    default_payment_method_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PaymentRecord(BaseModel):
    id: str
    user_id: str
    subscription_id: str | None = None
    provider: str = "stripe"
    provider_payment_id: str
    amount: int
    currency: str = "rub"
    status: PaymentStatus = "pending"
    description: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class InvoiceRecord(BaseModel):
    id: str
    user_id: str
    subscription_id: str | None = None
    provider: str = "stripe"
    provider_invoice_id: str
    amount: int
    currency: str = "rub"
    status: InvoiceStatus = "open"
    invoice_url: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class BillingEventRecord(BaseModel):
    id: str
    provider: str = "stripe"
    provider_event_id: str
    type: str
    status: Literal["received", "processed", "ignored", "failed"] = "received"
    payload_summary: str | None = None
    error: str | None = None
    processed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class UsageCounters(BaseModel):
    user_id: str
    period_key: str  # e.g. 2026-10
    experiments_used: int = 0
    updated_at: datetime = Field(default_factory=utcnow)


class CustomerMap(BaseModel):
    """Maps NEXA user → Stripe customer (no card data)."""

    user_id: str
    provider_customer_id: str
    email: str
    default_payment_method_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
