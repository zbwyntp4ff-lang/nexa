"""NEXA subscription plans and pricing (source of truth on the backend).

Amounts are in the smallest currency unit (kopecks for RUB).
Yearly prices intentionally encode a discount vs 12× monthly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PlanId = Literal["free", "starter", "pro", "business", "enterprise"]
BillingInterval = Literal["month", "year"]
FeatureId = Literal[
    "omniverse",
    "shadow",
    "what_if",
    "deep_research",
    "advanced_discoveries",
    "priority_ai",
    "team_workspace",
    "shared_projects",
    "permissions",
    "api_access",
    "analytics",
    "sso_saml",
    "dedicated_support",
    "custom_limits",
    "image_to_video",
]


@dataclass(frozen=True)
class PlanDefinition:
    id: PlanId
    name: str
    tagline: str
    monthly_amount: int  # kopecks; 0 = free; -1 = custom / contact sales
    yearly_amount: int  # kopecks for 12 months billed yearly; -1 = custom
    currency: str = "rub"
    popular: bool = False
    features: tuple[FeatureId, ...] = ()
    experiment_limit: int | None = 0  # None = unlimited; 0 = none
    highlight: str | None = None
    cta: str = "Get started"
    contact_sales: bool = False


# Yearly = 10× monthly → ~2 months free (~17% savings) for paid tiers.
PLANS: dict[PlanId, PlanDefinition] = {
    "free": PlanDefinition(
        id="free",
        name="Free",
        tagline="Start exploring NEXA",
        monthly_amount=0,
        yearly_amount=0,
        features=(),
        experiment_limit=0,
        cta="Continue free",
    ),
    "starter": PlanDefinition(
        id="starter",
        name="Starter",
        tagline="Reality Engine for solo builders",
        monthly_amount=29_900,
        yearly_amount=299_000,
        features=("omniverse", "shadow", "what_if", "image_to_video"),
        experiment_limit=25,
        cta="Choose Starter",
    ),
    "pro": PlanDefinition(
        id="pro",
        name="Pro",
        tagline="Deep research and serious exploration",
        monthly_amount=69_900,
        yearly_amount=699_000,
        popular=True,
        features=(
            "omniverse",
            "shadow",
            "what_if",
            "deep_research",
            "advanced_discoveries",
            "priority_ai",
            "image_to_video",
        ),
        experiment_limit=100,
        highlight="MOST POPULAR",
        cta="Choose Pro",
    ),
    "business": PlanDefinition(
        id="business",
        name="Business",
        tagline="Teams, shared work, and API access",
        monthly_amount=199_900,
        yearly_amount=1_999_000,
        features=(
            "omniverse",
            "shadow",
            "what_if",
            "deep_research",
            "advanced_discoveries",
            "priority_ai",
            "team_workspace",
            "shared_projects",
            "permissions",
            "api_access",
            "analytics",
            "image_to_video",
        ),
        experiment_limit=None,
        cta="Choose Business",
    ),
    "enterprise": PlanDefinition(
        id="enterprise",
        name="Enterprise",
        tagline="Custom limits, SSO, and dedicated support",
        monthly_amount=-1,
        yearly_amount=-1,
        features=(
            "omniverse",
            "shadow",
            "what_if",
            "deep_research",
            "advanced_discoveries",
            "priority_ai",
            "team_workspace",
            "shared_projects",
            "permissions",
            "api_access",
            "analytics",
            "sso_saml",
            "dedicated_support",
            "custom_limits",
            "image_to_video",
        ),
        experiment_limit=None,
        cta="Contact sales",
        contact_sales=True,
    ),
}

PLAN_ORDER: tuple[PlanId, ...] = ("free", "starter", "pro", "business", "enterprise")

FEATURE_LABELS: dict[FeatureId, str] = {
    "omniverse": "OMNIVERSE",
    "shadow": "SHADOW discoveries",
    "what_if": "WHAT IF?",
    "deep_research": "Deep Research",
    "advanced_discoveries": "Advanced discoveries",
    "priority_ai": "Priority AI",
    "team_workspace": "Team workspace",
    "shared_projects": "Shared projects",
    "permissions": "Permissions",
    "api_access": "API access",
    "analytics": "Analytics",
    "sso_saml": "SSO / SAML",
    "dedicated_support": "Dedicated support",
    "custom_limits": "Custom limits",
    "image_to_video": "Image-to-video",
}


def get_plan(plan_id: str) -> PlanDefinition:
    key = (plan_id or "free").strip().lower()
    return PLANS.get(key, PLANS["free"])  # type: ignore[arg-type]


def price_for(plan_id: PlanId, interval: BillingInterval) -> int:
    plan = get_plan(plan_id)
    if plan.contact_sales:
        return -1
    return plan.yearly_amount if interval == "year" else plan.monthly_amount


def yearly_savings_percent(plan_id: PlanId) -> int | None:
    plan = get_plan(plan_id)
    if plan.monthly_amount <= 0 or plan.yearly_amount <= 0:
        return None
    full = plan.monthly_amount * 12
    if full <= 0:
        return None
    saved = full - plan.yearly_amount
    return max(0, int(round(100 * saved / full)))
