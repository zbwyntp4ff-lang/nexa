"""Billing unit tests — plans, entitlements, webhook idempotency (no live Stripe)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.billing.entitlements import EntitlementService
from app.billing.errors import EntitlementDeniedError, UsageLimitExceededError
from app.billing.plans import PLANS, get_plan, yearly_savings_percent
from app.billing.store import BillingStore
from app.billing.store_models import BillingEventRecord, SubscriptionRecord, utcnow


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
