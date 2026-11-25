"""Billing unit tests — plans, entitlements, webhook idempotency (no live Stripe)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.auth.models import UserRecord
from app.billing.entitlements import EntitlementService
from app.billing.errors import (
    BillingNotConfiguredError,
    EntitlementDeniedError,
    UsageLimitExceededError,
    WebhookSignatureError,
)
from app.billing.plans import PLANS, get_plan, yearly_savings_percent
from app.billing.service import BillingService
from app.billing.store import BillingStore
from app.billing.store_models import BillingEventRecord, CustomerMap, SubscriptionRecord, utcnow


class _FakeStripeProvider:
    """In-memory Stripe stand-in — never calls the network."""

    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured
        self.events: list[dict[str, Any]] = []
        self.subscriptions: dict[str, dict[str, Any]] = {}

    def construct_event(self, payload: bytes, signature: str) -> dict[str, Any]:
        if signature != "sig_ok":
            raise ValueError("bad signature")
        import json

        return json.loads(payload.decode("utf-8"))

    def retrieve_subscription(self, sub_id: str) -> dict[str, Any]:
        return self.subscriptions[sub_id]

    def create_customer(self, **_kwargs: Any) -> dict[str, str]:
        return {"id": "cus_test"}

    def create_checkout_session(self, **_kwargs: Any) -> dict[str, str]:
        return {"id": "cs_test", "url": "https://checkout.test/session"}

    def create_portal_session(self, **_kwargs: Any) -> dict[str, str]:
        return {"url": "https://billing.test/portal"}

    def cancel_subscription(self, sub_id: str, *, at_period_end: bool = True) -> dict[str, Any]:
        sub = dict(self.subscriptions[sub_id])
        sub["cancel_at_period_end"] = at_period_end
        sub["status"] = "active" if at_period_end else "canceled"
        self.subscriptions[sub_id] = sub
        return sub

    def resume_subscription(self, sub_id: str) -> dict[str, Any]:
        sub = dict(self.subscriptions[sub_id])
        sub["cancel_at_period_end"] = False
        self.subscriptions[sub_id] = sub
        return sub

    def list_payment_methods(self, _customer_id: str) -> list[dict]:
        return []

    def detach_payment_method(self, _pm_id: str) -> None:
        return None


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "stripe_secret_key": None,
        "stripe_webhook_secret": None,
        "billing_public_base_url": "http://localhost:4820",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _user(uid: str = "u1") -> UserRecord:
    return UserRecord(
        id=uid,
        email=f"{uid}@example.com",
        username=uid,
        first_name="Test",
        last_name="User",
        password_hash="x",
        email_verified=True,
        is_active=True,
    )


def test_plans_include_five_tiers_and_pro_popular():
    assert set(PLANS) == {"free", "starter", "pro", "business", "enterprise"}
    assert PLANS["pro"].popular is True
    assert PLANS["pro"].monthly_amount == 69_900
    assert PLANS["starter"].experiment_limit == 25
    assert PLANS["pro"].experiment_limit == 100
    assert yearly_savings_percent("pro") == 17


def test_entitlements_free_blocks_omniverse(tmp_path: Path):
    store = BillingStore(tmp_path / "billing.json")
    ents = EntitlementService(store)
    assert ents.get_plan("u1").id == "free"
    assert ents.can_use_feature("u1", "omniverse") is False
    with pytest.raises(EntitlementDeniedError):
        ents.require_feature("u1", "omniverse")


def test_entitlements_starter_allows_omniverse_and_limits_experiments(tmp_path: Path):
    store = BillingStore(tmp_path / "billing.json")
    store.save_subscription(
        SubscriptionRecord(
            id="sub1",
            user_id="u1",
            plan="starter",
            status="active",
            provider_subscription_id="sub_test",
        )
    )
    ents = EntitlementService(store)
    assert ents.can_use_feature("u1", "omniverse") is True
    assert ents.can_use_feature("u1", "deep_research") is False
    for _ in range(25):
        ents.record_experiment("u1")
    with pytest.raises(UsageLimitExceededError):
        ents.record_experiment("u1")


def test_billing_event_idempotency_index(tmp_path: Path):
    store = BillingStore(tmp_path / "billing.json")
    ev = BillingEventRecord(
        id="bev1",
        provider_event_id="evt_123",
        type="checkout.session.completed",
        status="processed",
        processed_at=utcnow(),
    )
    store.save_event(ev)
    assert store.get_event_by_provider_id("evt_123") is not None
    # reload
    store2 = BillingStore(tmp_path / "billing.json")
    again = store2.get_event_by_provider_id("evt_123")
    assert again is not None
    assert again.status == "processed"


def test_plan_serialization_public_fields():
    plan = get_plan("business")
    assert "api_access" in plan.features
    assert plan.contact_sales is False
    assert get_plan("enterprise").contact_sales is True


def test_provider_status_unconfigured_and_test_modes(tmp_path: Path):
    store = BillingStore(tmp_path / "b.json")
    ents = EntitlementService(store)
    svc = BillingService(
        store,
        _FakeStripeProvider(configured=False),
        ents,
        _settings(),
    )
    status = svc.provider_status()
    assert status["configured"] is False
    assert status["mode"] == "unconfigured"
    assert status["activation"] == "webhook_only"

    svc2 = BillingService(
        store,
        _FakeStripeProvider(configured=True),
        ents,
        _settings(
            stripe_secret_key="sk_test_xxx",
            stripe_webhook_secret="whsec_xxx",
        ),
    )
    assert svc2.provider_status()["mode"] == "test"


def test_checkout_blocked_when_unconfigured(tmp_path: Path):
    store = BillingStore(tmp_path / "b.json")
    svc = BillingService(
        store,
        _FakeStripeProvider(configured=False),
        EntitlementService(store),
        _settings(),
    )
    with pytest.raises(BillingNotConfiguredError):
        svc.create_checkout(_user(), plan_id="starter", interval="month")


def test_webhook_success_duplicate_and_bad_signature(tmp_path: Path):
    import json

    store = BillingStore(tmp_path / "b.json")
    provider = _FakeStripeProvider(configured=True)
    provider.subscriptions["sub_1"] = {
        "id": "sub_1",
        "status": "active",
        "customer": "cus_1",
        "cancel_at_period_end": False,
        "current_period_start": 1_700_000_000,
        "current_period_end": 1_700_268_000,
        "metadata": {"nexa_user_id": "u1", "nexa_plan": "pro", "nexa_interval": "month"},
        "items": {"data": []},
    }
    store.save_customer(
        CustomerMap(user_id="u1", provider_customer_id="cus_1", email="u1@example.com")
    )
    svc = BillingService(
        store,
        provider,
        EntitlementService(store),
        _settings(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x"),
    )

    event = {
        "id": "evt_pay_1",
        "type": "customer.subscription.created",
        "data": {"object": provider.subscriptions["sub_1"]},
    }
    payload = json.dumps(event).encode("utf-8")

    with pytest.raises(WebhookSignatureError):
        svc.handle_webhook(payload, "sig_bad")

    first = svc.handle_webhook(payload, "sig_ok")
    assert first["status"] == "processed"
    snap = svc._entitlements.snapshot("u1")
    assert snap["plan"] == "pro"

    second = svc.handle_webhook(payload, "sig_ok")
    assert second["status"] == "duplicate"


def test_webhook_cancel_moves_to_free(tmp_path: Path):
    import json

    store = BillingStore(tmp_path / "b.json")
    provider = _FakeStripeProvider(configured=True)
    store.save_subscription(
        SubscriptionRecord(
            id="sub_local",
            user_id="u1",
            plan="starter",
            status="active",
            provider_subscription_id="sub_del",
        )
    )
    svc = BillingService(
        store,
        provider,
        EntitlementService(store),
        _settings(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x"),
    )
    event = {
        "id": "evt_cancel_1",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_del",
                "customer": "cus_1",
                "metadata": {"nexa_user_id": "u1"},
            }
        },
    }
    result = svc.handle_webhook(json.dumps(event).encode("utf-8"), "sig_ok")
    assert result["status"] == "processed"
    assert svc._entitlements.snapshot("u1")["plan"] == "free"



def test_stale_deleted_subscription_event_does_not_downgrade_current_plan(tmp_path: Path):
    import json

    store = BillingStore(tmp_path / "billing.json")
    provider = _FakeStripeProvider(configured=True)
    store.save_subscription(
        SubscriptionRecord(
            id="sub_old_local",
            user_id="u1",
            plan="starter",
            status="canceled",
            provider_subscription_id="sub_old",
        )
    )
    store.save_subscription(
        SubscriptionRecord(
            id="sub_new_local",
            user_id="u1",
            plan="pro",
            status="active",
            provider_subscription_id="sub_new",
        )
    )
    svc = BillingService(
        store,
        provider,
        EntitlementService(store),
        _settings(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x"),
    )
    event = {
        "id": "evt_old_sub_deleted",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_old",
                "customer": "cus_1",
                "metadata": {"nexa_user_id": "u1"},
            }
        },
    }

    result = svc.handle_webhook(json.dumps(event).encode("utf-8"), "sig_ok")

    assert result["status"] == "processed"
    current = store.get_subscription_for_user("u1")
    assert current is not None
    assert current.provider_subscription_id == "sub_new"
    assert current.plan == "pro"
    assert svc._entitlements.snapshot("u1")["plan"] == "pro"


def test_account_deletion_cancels_live_stripe_subscription(tmp_path: Path):
    store = BillingStore(tmp_path / "billing.json")
    provider = _FakeStripeProvider(configured=True)
    store.save_subscription(
        SubscriptionRecord(
            id="sub_live_local",
            user_id="u1",
            plan="pro",
            status="active",
            provider_subscription_id="sub_live",
        )
    )
    provider.subscriptions["sub_live"] = {
        "id": "sub_live",
        "status": "active",
    }
    svc = BillingService(
        store,
        provider,
        EntitlementService(store),
        _settings(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x"),
    )

    assert svc.cancel_for_account_deletion("u1") is True
    assert provider.subscriptions["sub_live"]["status"] == "canceled"
    assert provider.subscriptions["sub_live"]["cancel_at_period_end"] is False
