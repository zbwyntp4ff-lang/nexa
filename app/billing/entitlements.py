"""Entitlements: plan, usage, and feature checks (server-side only)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.billing.errors import EntitlementDeniedError, UsageLimitExceededError
from app.billing.plans import FEATURE_LABELS, FeatureId, PlanDefinition, PlanId, get_plan
from app.billing.store import BillingStore
from app.billing.store_models import SubscriptionRecord, UsageCounters, utcnow


ACTIVE_STATUSES = frozenset({"active", "trialing"})


class EntitlementService:
    def __init__(self, store: BillingStore) -> None:
        self._store = store

    def get_subscription(self, user_id: str) -> SubscriptionRecord:
        sub = self._store.get_subscription_for_user(user_id)
        if sub and sub.status in ACTIVE_STATUSES:
            return sub
        if sub and sub.status == "canceled" and sub.current_period_end:
            end = sub.current_period_end
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end > datetime.now(timezone.utc) and sub.cancel_at_period_end:
                # Still entitled until period end
                return sub
        if sub:
            # past_due / unpaid still expose the record but plan features fall back carefully
            if sub.status in {"past_due", "unpaid"} and sub.plan != "free":
                return sub
        return SubscriptionRecord(id=f"free_{user_id}", user_id=user_id, plan="free", status="active")

    def get_plan(self, user_id: str) -> PlanDefinition:
        return get_plan(self.get_subscription(user_id).plan)

    def period_key(self, when: datetime | None = None) -> str:
        dt = when or utcnow()
        return f"{dt.year:04d}-{dt.month:02d}"

    def get_usage(self, user_id: str) -> dict:
        plan = self.get_plan(user_id)
        key = self.period_key()
        counters = self._store.get_usage(user_id, key) or UsageCounters(user_id=user_id, period_key=key)
        limit = plan.experiment_limit
        return {
            "period": key,
            "experiments_used": counters.experiments_used,
            "experiments_limit": limit,
            "experiments_remaining": None if limit is None else max(0, limit - counters.experiments_used),
            "plan": plan.id,
        }

    def can_use_feature(self, user_id: str, feature: FeatureId | str) -> bool:
        plan = self.get_plan(user_id)
        feat = str(feature).strip().lower()
        if feat == "experiments":
            usage = self.get_usage(user_id)
            limit = usage["experiments_limit"]
            if limit is None:
                return True
            if limit == 0:
                return False
            return usage["experiments_used"] < limit
        return feat in plan.features

    def require_feature(self, user_id: str, feature: FeatureId | str) -> None:
        if not self.can_use_feature(user_id, feature):
            label = FEATURE_LABELS.get(feature, str(feature))  # type: ignore[arg-type]
            raise EntitlementDeniedError(
                f"Plan '{self.get_plan(user_id).id}' does not include {label}."
            )

    def record_experiment(self, user_id: str) -> UsageCounters:
        self.require_feature(user_id, "omniverse")
        if not self.can_use_feature(user_id, "experiments"):
            raise UsageLimitExceededError(
                f"Experiment limit reached for plan '{self.get_plan(user_id).id}'."
            )
        key = self.period_key()
        counters = self._store.get_usage(user_id, key) or UsageCounters(user_id=user_id, period_key=key)
        counters.experiments_used += 1
        counters.updated_at = utcnow()
        return self._store.save_usage(counters)

    def snapshot(self, user_id: str) -> dict:
        sub = self.get_subscription(user_id)
        plan = get_plan(sub.plan)
        return {
            "plan": plan.id,
            "plan_name": plan.name,
            "status": sub.status,
            "billing_interval": sub.billing_interval,
            "features": list(plan.features),
            "experiment_limit": plan.experiment_limit,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "usage": self.get_usage(user_id),
        }
