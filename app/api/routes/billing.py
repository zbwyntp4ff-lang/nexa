"""Billing HTTP API — plans, checkout, portal, webhook, entitlements."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import get_billing_service, get_entitlement_service
from app.api.routes.auth import get_current_user
from app.auth.models import UserRecord
from app.billing.entitlements import EntitlementService
from app.billing.errors import RateLimitedError, WebhookSignatureError
from app.billing.rate_limit import billing_action_limiter, webhook_ip_limiter
from app.billing.service import BillingService
from app.models.billing_api import (
    CheckoutRequest,
    DetachPaymentMethodRequest,
    EntitlementCheckRequest,
    PortalRequest,
)

router = APIRouter(tags=["billing"])


@router.get("/api/billing/plans")
async def list_plans(
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    return {"plans": billing.list_plans_public(), "currency": "rub"}


@router.get("/api/billing/me")
async def billing_me(
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    return billing.billing_overview(user)


@router.post("/api/billing/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    billing_action_limiter.check(f"checkout:{user.id}")
    return billing.create_checkout(
        user,
        plan_id=body.plan,
        interval=body.interval,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )


@router.post("/api/billing/portal")
async def create_portal(
    body: PortalRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    billing_action_limiter.check(f"portal:{user.id}")
    return billing.create_portal(user, return_url=body.return_url)


@router.post("/api/billing/cancel")
async def cancel_subscription(
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    billing_action_limiter.check(f"cancel:{user.id}")
    sub = billing.cancel_subscription(user)
    return {
        "plan": sub.plan,
        "status": sub.status,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.post("/api/billing/resume")
async def resume_subscription(
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    billing_action_limiter.check(f"resume:{user.id}")
    sub = billing.resume_subscription(user)
    return {
        "plan": sub.plan,
        "status": sub.status,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.get("/api/billing/payment-methods")
async def payment_methods(
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, Any]:
    return {"payment_methods": billing.list_payment_methods(user)}


@router.post("/api/billing/payment-methods/detach")
async def detach_payment_method(
    body: DetachPaymentMethodRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> dict[str, str]:
    billing_action_limiter.check(f"detach:{user.id}")
    billing.detach_payment_method(user, body.payment_method_id)
    return {"status": "detached"}


@router.get("/api/billing/entitlements")
async def entitlements(
    user: Annotated[UserRecord, Depends(get_current_user)],
    ents: Annotated[EntitlementService, Depends(get_entitlement_service)],
) -> dict[str, Any]:
    return ents.snapshot(user.id)


@router.post("/api/billing/entitlements/check")
async def check_entitlement(
    body: EntitlementCheckRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    ents: Annotated[EntitlementService, Depends(get_entitlement_service)],
) -> dict[str, Any]:
    allowed = ents.can_use_feature(user.id, body.feature)
    return {"feature": body.feature, "allowed": allowed, "plan": ents.get_plan(user.id).id}


@router.post("/api/billing/usage/experiment")
async def record_experiment_usage(
    user: Annotated[UserRecord, Depends(get_current_user)],
    ents: Annotated[EntitlementService, Depends(get_entitlement_service)],
) -> dict[str, Any]:
    ents.record_experiment(user.id)
    return ents.get_usage(user.id)


@router.post("/api/billing/webhook")
async def stripe_webhook(
    request: Request,
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> JSONResponse:
    """Stripe webhook — signature verified; subscription activates only here."""
    client = request.client.host if request.client else "unknown"
    try:
        webhook_ip_limiter.check(f"wh:{client}")
    except RateLimitedError:
        return JSONResponse(status_code=429, content={"error": "RateLimited", "message": "Too many requests."})

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not signature:
        raise WebhookSignatureError("Missing Stripe-Signature header.")
    result = billing.handle_webhook(payload, signature)
    return JSONResponse(content=result)
