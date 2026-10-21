"""Billing service: checkout, portal, cancel/resume, webhook processing."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from app.auth.models import UserRecord
from app.billing.entitlements import EntitlementService
from app.billing.errors import (
    BillingNotConfiguredError,
    PlanNotPurchasableError,
    WebhookSignatureError,
)
from app.billing.plans import (
    FEATURE_LABELS,
    PLAN_ORDER,
    BillingInterval,
    PlanId,
    get_plan,
    yearly_savings_percent,
)
from app.billing.store import BillingStore
from app.billing.store_models import (
    BillingEventRecord,
    CustomerMap,
    InvoiceRecord,
    PaymentRecord,
    SubscriptionRecord,
    utcnow,
)
from app.billing.stripe_provider import StripeBillingProvider
from app.config.settings import Settings
from app.core.logging_config import get_logger

logger = get_logger("nexa.billing")


def _uid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _ts(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc)


class BillingService:
    def __init__(
        self,
        store: BillingStore,
        provider: StripeBillingProvider,
        entitlements: EntitlementService,
        settings: Settings,
    ) -> None:
        self._store = store
        self._provider = provider
        self._entitlements = entitlements
        self._settings = settings

    # --- catalog ----------------------------------------------------------
    def list_plans_public(self) -> list[dict]:
        out: list[dict] = []
        for plan_id in PLAN_ORDER:
            plan = get_plan(plan_id)
            savings = yearly_savings_percent(plan_id)
            out.append(
                {
                    "id": plan.id,
                    "name": plan.name,
                    "tagline": plan.tagline,
                    "currency": plan.currency,
                    "monthly_amount": plan.monthly_amount,
                    "yearly_amount": plan.yearly_amount,
                    "popular": plan.popular,
                    "highlight": plan.highlight,
                    "cta": plan.cta,
                    "contact_sales": plan.contact_sales,
                    "features": [
                        {"id": f, "label": FEATURE_LABELS.get(f, f)} for f in plan.features
                    ],
                    "experiment_limit": plan.experiment_limit,
                    "yearly_savings_percent": savings,
                }
            )
        return out

    # --- customer ---------------------------------------------------------
    def _ensure_customer(self, user: UserRecord) -> CustomerMap:
        existing = self._store.get_customer(user.id)
        if existing:
            return existing
        if not self._provider.configured:
            raise BillingNotConfiguredError()
        name = f"{user.first_name} {user.last_name}".strip()
        customer = self._provider.create_customer(email=user.email, name=name, user_id=user.id)
        mapped = CustomerMap(
            user_id=user.id,
            provider_customer_id=customer["id"],
            email=user.email,
        )
        return self._store.save_customer(mapped)

    # --- checkout / portal ------------------------------------------------
    def create_checkout(
        self,
        user: UserRecord,
        *,
        plan_id: PlanId,
        interval: BillingInterval,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict:
        plan = get_plan(plan_id)
        if plan.id == "free":
            raise PlanNotPurchasableError("Free plan does not require payment.")
        if plan.contact_sales:
            raise PlanNotPurchasableError("Enterprise requires contacting sales.")
        if not self._provider.configured:
            raise BillingNotConfiguredError()

        customer = self._ensure_customer(user)
        base = (self._settings.billing_public_base_url or "http://localhost:4820").rstrip("/")
        success = success_url or f"{base}/pricing?checkout=success"
        cancel = cancel_url or f"{base}/pricing?checkout=cancel"
        session = self._provider.create_checkout_session(
            customer_id=customer.provider_customer_id,
            plan=plan,
            interval=interval,
            success_url=success,
            cancel_url=cancel,
            user_id=user.id,
        )
        return {
            "checkout_url": session["url"],
            "session_id": session["id"],
            "plan": plan.id,
            "interval": interval,
        }

    def create_portal(self, user: UserRecord, *, return_url: str | None = None) -> dict:
        if not self._provider.configured:
            raise BillingNotConfiguredError()
        customer = self._ensure_customer(user)
        base = (self._settings.billing_public_base_url or "http://localhost:4820").rstrip("/")
        url = return_url or f"{base}/?settings=billing"
        session = self._provider.create_portal_session(
            customer_id=customer.provider_customer_id,
            return_url=url,
        )
        return {"portal_url": session["url"]}

    def cancel_subscription(self, user: UserRecord) -> SubscriptionRecord:
        sub = self._store.get_subscription_for_user(user.id)
        if not sub or not sub.provider_subscription_id or sub.plan == "free":
            raise PlanNotPurchasableError("No active paid subscription to cancel.")
        updated = self._provider.cancel_subscription(sub.provider_subscription_id, at_period_end=True)
        return self._apply_stripe_subscription(user.id, updated, fallback_plan=sub.plan)

    def resume_subscription(self, user: UserRecord) -> SubscriptionRecord:
        sub = self._store.get_subscription_for_user(user.id)
        if not sub or not sub.provider_subscription_id:
            raise PlanNotPurchasableError("No subscription to resume.")
        updated = self._provider.resume_subscription(sub.provider_subscription_id)
        return self._apply_stripe_subscription(user.id, updated, fallback_plan=sub.plan)

    def list_payment_methods(self, user: UserRecord) -> list[dict]:
        customer = self._store.get_customer(user.id)
        if not customer or not self._provider.configured:
            return []
        methods = self._provider.list_payment_methods(customer.provider_customer_id)
        out = []
        for m in methods:
            card = m.get("card") or {}
            out.append(
                {
                    "id": m["id"],
                    "brand": card.get("brand"),
                    "last4": card.get("last4"),
                    "exp_month": card.get("exp_month"),
                    "exp_year": card.get("exp_year"),
                    # Never expose full PAN / CVV — Stripe only returns tokenized refs.
                }
            )
        return out

    def detach_payment_method(self, user: UserRecord, payment_method_id: str) -> None:
        customer = self._store.get_customer(user.id)
        if not customer:
            raise PlanNotPurchasableError("No billing customer on file.")
        # Verify the PM belongs to this customer via list
        owned = {m["id"] for m in self.list_payment_methods(user)}
        if payment_method_id not in owned:
            raise PlanNotPurchasableError("Payment method not found for this account.")
        self._provider.detach_payment_method(payment_method_id)

    def provider_status(self) -> dict[str, str | bool]:
        """Honest payment-provider readiness (never claim live payments without keys)."""
        key = (self._settings.stripe_secret_key or "").strip()
        wh = (self._settings.stripe_webhook_secret or "").strip()
        configured = bool(key and wh)
        if not configured:
            mode = "unconfigured"
        elif key.startswith("sk_test_"):
            mode = "test"
        elif key.startswith("sk_live_"):
            mode = "live"
        else:
            mode = "unknown"
        return {
            "provider": "stripe",
            "configured": configured,
            "mode": mode,
            # Plans are RUB; Stripe availability depends on the legal operator's country.
            "currency": "rub",
            "activation": "webhook_only",
        }

    def billing_overview(self, user: UserRecord) -> dict:
        snap = self._entitlements.snapshot(user.id)
        sub = self._store.get_subscription_for_user(user.id)
        status = self.provider_status()
        return {
            **snap,
            "provider_configured": bool(status["configured"]),
            "provider_status": status,
            "subscription_id": sub.id if sub else None,
            "provider_subscription_id": sub.provider_subscription_id if sub else None,
            "payment_methods": self.list_payment_methods(user),
            "invoices": [
                {
                    "id": i.id,
                    "amount": i.amount,
                    "currency": i.currency,
                    "status": i.status,
                    "invoice_url": i.invoice_url,
                    "created_at": i.created_at.isoformat(),
                }
                for i in self._store.list_invoices_for_user(user.id)[:50]
            ],
            "payments": [
                {
                    "id": p.id,
                    "amount": p.amount,
                    "currency": p.currency,
                    "status": p.status,
                    "description": p.description,
                    "created_at": p.created_at.isoformat(),
                }
                for p in self._store.list_payments_for_user(user.id)[:50]
            ],
        }

    # --- webhook ----------------------------------------------------------
    def handle_webhook(self, payload: bytes, signature: str) -> dict:
        if not self._provider.configured:
            raise BillingNotConfiguredError()
        try:
            event = self._provider.construct_event(payload, signature)
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook signature failed: %s", exc)
            raise WebhookSignatureError() from exc

        event_id = event["id"]
        event_type = event["type"]
        existing = self._store.get_event_by_provider_id(event_id)
        if existing and existing.status == "processed":
            return {"status": "duplicate", "event_id": event_id}

        record = existing or BillingEventRecord(
            id=_uid("bev"),
            provider_event_id=event_id,
            type=event_type,
            status="received",
        )
        self._store.save_event(record)

        try:
            data_object = event["data"]["object"]
            if event_type == "checkout.session.completed":
                self._on_checkout_completed(data_object)
            elif event_type in {
                "customer.subscription.created",
                "customer.subscription.updated",
            }:
                self._on_subscription_upsert(data_object)
            elif event_type == "customer.subscription.deleted":
                self._on_subscription_deleted(data_object)
            elif event_type == "invoice.paid":
                self._on_invoice(data_object, status="paid")
            elif event_type in {"invoice.payment_failed", "invoice.finalized"}:
                status = "open" if event_type == "invoice.finalized" else "open"
                self._on_invoice(data_object, status=status if event_type != "invoice.payment_failed" else "uncollectible")
            elif event_type == "payment_intent.succeeded":
                self._on_payment_intent(data_object, status="succeeded")
            elif event_type == "payment_intent.payment_failed":
                self._on_payment_intent(data_object, status="failed")
            else:
                record.status = "ignored"
                record.processed_at = utcnow()
                self._store.save_event(record)
                return {"status": "ignored", "event_id": event_id, "type": event_type}

            record.status = "processed"
            record.processed_at = utcnow()
            record.payload_summary = event_type
            self._store.save_event(record)
            return {"status": "processed", "event_id": event_id, "type": event_type}
        except Exception as exc:  # noqa: BLE001
            logger.exception("webhook processing failed event=%s", event_id)
            record.status = "failed"
            record.error = str(exc)[:500]
            record.processed_at = utcnow()
            self._store.save_event(record)
            raise

    def _resolve_user_id(self, obj: dict, metadata: dict | None = None) -> str | None:
        meta = metadata or obj.get("metadata") or {}
        if meta.get("nexa_user_id"):
            return str(meta["nexa_user_id"])
        if obj.get("client_reference_id"):
            return str(obj["client_reference_id"])
        customer_id = obj.get("customer")
        if isinstance(customer_id, str):
            return self._store.get_user_id_by_customer(customer_id)
        return None

    def _on_checkout_completed(self, session: dict) -> None:
        user_id = self._resolve_user_id(session)
        if not user_id:
            logger.warning("checkout.session.completed without nexa_user_id")
            return
        sub_id = session.get("subscription")
        if not sub_id:
            return
        stripe_sub = self._provider.retrieve_subscription(sub_id)
        plan = (session.get("metadata") or {}).get("nexa_plan") or (
            stripe_sub.get("metadata") or {}
        ).get("nexa_plan")
        self._apply_stripe_subscription(user_id, stripe_sub, fallback_plan=plan or "starter")

    def _on_subscription_upsert(self, stripe_sub: dict) -> None:
        user_id = self._resolve_user_id(stripe_sub, stripe_sub.get("metadata"))
        if not user_id:
            customer_id = stripe_sub.get("customer")
            if isinstance(customer_id, str):
                user_id = self._store.get_user_id_by_customer(customer_id)
        if not user_id:
            logger.warning("subscription event without user mapping")
            return
        plan = (stripe_sub.get("metadata") or {}).get("nexa_plan") or "starter"
        self._apply_stripe_subscription(user_id, stripe_sub, fallback_plan=plan)

    def _on_subscription_deleted(self, stripe_sub: dict) -> None:
        existing = self._store.get_subscription_by_provider_id(stripe_sub["id"])
        user_id = existing.user_id if existing else self._resolve_user_id(stripe_sub, stripe_sub.get("metadata"))
        if not user_id:
            return
        record = existing or SubscriptionRecord(id=_uid("sub"), user_id=user_id)
        record.plan = "free"
        record.status = "canceled"
        record.cancel_at_period_end = False
        record.provider_subscription_id = stripe_sub["id"]
        record.updated_at = utcnow()
        self._store.save_subscription(record)

    def _on_invoice(self, invoice: dict, *, status: str) -> None:
        user_id = self._resolve_user_id(invoice, invoice.get("metadata"))
        if not user_id:
            customer_id = invoice.get("customer")
            if isinstance(customer_id, str):
                user_id = self._store.get_user_id_by_customer(customer_id)
        if not user_id:
            return
        provider_invoice_id = invoice["id"]
        existing = self._store.get_invoice_by_provider_id(provider_invoice_id)
        sub = None
        if invoice.get("subscription"):
            sub = self._store.get_subscription_by_provider_id(invoice["subscription"])
        record = existing or InvoiceRecord(
            id=_uid("inv"),
            user_id=user_id,
            provider_invoice_id=provider_invoice_id,
            amount=int(invoice.get("amount_paid") or invoice.get("amount_due") or 0),
            currency=(invoice.get("currency") or "rub").lower(),
        )
        record.user_id = user_id
        record.subscription_id = sub.id if sub else record.subscription_id
        record.amount = int(invoice.get("amount_paid") or invoice.get("amount_due") or record.amount)
        record.currency = (invoice.get("currency") or record.currency).lower()
        record.status = status  # type: ignore[assignment]
        record.invoice_url = invoice.get("hosted_invoice_url") or invoice.get("invoice_pdf")
        record.period_start = _ts(invoice.get("period_start"))
        record.period_end = _ts(invoice.get("period_end"))
        record.updated_at = utcnow()
        self._store.save_invoice(record)

        # Mirror a payment row when paid
        if status == "paid" and invoice.get("payment_intent"):
            pi = invoice["payment_intent"]
            if isinstance(pi, str):
                self._upsert_payment(
                    user_id=user_id,
                    subscription_id=sub.id if sub else None,
                    provider_payment_id=pi,
                    amount=record.amount,
                    currency=record.currency,
                    status="succeeded",
                    description=f"Invoice {provider_invoice_id}",
                )

    def _on_payment_intent(self, pi: dict, *, status: str) -> None:
        user_id = self._resolve_user_id(pi, pi.get("metadata"))
        if not user_id:
            customer_id = pi.get("customer")
            if isinstance(customer_id, str):
                user_id = self._store.get_user_id_by_customer(customer_id)
        if not user_id:
            return
        self._upsert_payment(
            user_id=user_id,
            subscription_id=None,
            provider_payment_id=pi["id"],
            amount=int(pi.get("amount") or 0),
            currency=(pi.get("currency") or "rub").lower(),
            status=status,  # type: ignore[arg-type]
            description=pi.get("description"),
        )

    def _upsert_payment(
        self,
        *,
        user_id: str,
        subscription_id: str | None,
        provider_payment_id: str,
        amount: int,
        currency: str,
        status: str,
        description: str | None,
    ) -> PaymentRecord:
        existing = self._store.get_payment_by_provider_id(provider_payment_id)
        record = existing or PaymentRecord(
            id=_uid("pay"),
            user_id=user_id,
            provider_payment_id=provider_payment_id,
            amount=amount,
            currency=currency,
        )
        record.user_id = user_id
        record.subscription_id = subscription_id or record.subscription_id
        record.amount = amount
        record.currency = currency
        record.status = status  # type: ignore[assignment]
        record.description = description
        record.updated_at = utcnow()
        return self._store.save_payment(record)

    def _apply_stripe_subscription(
        self, user_id: str, stripe_sub: Any, *, fallback_plan: str
    ) -> SubscriptionRecord:
        data = stripe_sub if isinstance(stripe_sub, dict) else dict(stripe_sub)
        existing = self._store.get_subscription_by_provider_id(data["id"]) or self._store.get_subscription_for_user(
            user_id
        )
        record = existing or SubscriptionRecord(id=_uid("sub"), user_id=user_id)
        meta = data.get("metadata") or {}
        plan_id = (meta.get("nexa_plan") or fallback_plan or "starter").lower()
        if plan_id not in {"free", "starter", "pro", "business", "enterprise"}:
            plan_id = "starter"
        interval = (meta.get("nexa_interval") or "month").lower()
        if interval not in {"month", "year"}:
            # Infer from Stripe items
            items = (data.get("items") or {}).get("data") or []
            if items:
                rec = ((items[0].get("price") or {}).get("recurring") or {}).get("interval")
                interval = "year" if rec == "year" else "month"

        record.user_id = user_id
        record.plan = plan_id  # type: ignore[assignment]
        record.status = data.get("status") or "active"  # type: ignore[assignment]
        record.billing_interval = interval  # type: ignore[assignment]
        record.provider = "stripe"
        record.provider_customer_id = data.get("customer")
        record.provider_subscription_id = data["id"]
        record.current_period_start = _ts(data.get("current_period_start"))
        record.current_period_end = _ts(data.get("current_period_end"))
        record.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
        default_pm = data.get("default_payment_method")
        if isinstance(default_pm, str):
            record.default_payment_method_id = default_pm
        record.updated_at = utcnow()
        saved = self._store.save_subscription(record)

        # Keep customer map in sync
        if record.provider_customer_id:
            cust = self._store.get_customer(user_id)
            if cust:
                cust.provider_customer_id = record.provider_customer_id
                cust.default_payment_method_id = record.default_payment_method_id
                cust.updated_at = utcnow()
                self._store.save_customer(cust)
        return saved
