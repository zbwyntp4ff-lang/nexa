"""HTTP models for billing endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BillingInterval = Literal["month", "year"]
PlanId = Literal["free", "starter", "pro", "business", "enterprise"]


class CheckoutRequest(BaseModel):
    plan: PlanId
    interval: BillingInterval = "month"
    success_url: str | None = None
    cancel_url: str | None = None


class PortalRequest(BaseModel):
    return_url: str | None = None


class DetachPaymentMethodRequest(BaseModel):
    payment_method_id: str = Field(..., min_length=3, max_length=128)


class EntitlementCheckRequest(BaseModel):
    feature: str = Field(..., min_length=1, max_length=64)


class RecordExperimentRequest(BaseModel):
    """Optional client hint; server remains source of truth."""

    count: int = Field(default=1, ge=1, le=10)
