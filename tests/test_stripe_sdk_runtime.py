"""Contract tests for the Stripe 17 module-level API used by NEXA."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from app.billing.plans import get_plan
from app.billing.stripe_provider import StripeBillingProvider


def _settings():
    return SimpleNamespace(
        stripe_secret_key="sk_test_fake",
        stripe_webhook_secret="whsec_fake",
        stripe_price_starter_monthly=None,
        stripe_price_starter_yearly=None,
        stripe_price_pro_monthly=None,
        stripe_price_pro_yearly=None,
        stripe_price_business_monthly=None,
        stripe_price_business_yearly=None,
    )


def test_stripe_17_checkout_customer_portal_and_subscription_api(monkeypatch):
    calls = []

    def record(name):
        def invoke(*args, **kwargs):
            calls.append((name, args, kwargs))
            if name.endswith("list"):
                return SimpleNamespace(data=[{"id": "pm_1", "card": {"last4": "4242"}}])
            if name == "Webhook.construct_event":
                return {"id": "evt_1"}
            if name == "Subscription.retrieve":
                return {"id": "sub_1"}
            if name == "PaymentMethod.detach":
                return {"id": args[0]}
            return {"id": "obj_1", "url": "https://stripe.test/session"}
        return invoke

    stripe = SimpleNamespace(
        api_key=None,
        Customer=SimpleNamespace(create=record("Customer.create")),
        checkout=SimpleNamespace(Session=SimpleNamespace(create=record("checkout.Session.create"))),
        billing_portal=SimpleNamespace(Session=SimpleNamespace(create=record("billing_portal.Session.create"))),
        Subscription=SimpleNamespace(
            modify=record("Subscription.modify"),
            cancel=record("Subscription.cancel"),
            retrieve=record("Subscription.retrieve"),
        ),
        PaymentMethod=SimpleNamespace(
            list=record("PaymentMethod.list"),
            detach=record("PaymentMethod.detach"),
        ),
        Webhook=SimpleNamespace(construct_event=record("Webhook.construct_event")),
    )
    monkeypatch.setitem(sys.modules, "stripe", stripe)

    provider = StripeBillingProvider(_settings())
    customer = provider.create_customer(email="test@example.com", name="Test", user_id="u1")
    checkout = provider.create_checkout_session(
        customer_id=customer["id"],
        plan=get_plan("starter"),
        interval="month",
        success_url="https://nexa.test/success",
        cancel_url="https://nexa.test/cancel",
        user_id="u1",
    )
    portal = provider.create_portal_session(
        customer_id=customer["id"], return_url="https://nexa.test/account"
    )
    provider.cancel_subscription("sub_1", at_period_end=True)
    provider.cancel_subscription("sub_2", at_period_end=False)
    provider.resume_subscription("sub_1")
    provider.retrieve_subscription("sub_1")
    methods = provider.list_payment_methods("cus_1")
    detached = provider.detach_payment_method("pm_1")
    event = provider.construct_event(b"{}", "sig_test")

    assert stripe.api_key == "sk_test_fake"
    assert checkout["url"].startswith("https://stripe.test/")
    assert portal["url"].startswith("https://stripe.test/")
    assert methods[0]["id"] == "pm_1"
    assert detached["id"] == "pm_1"
    assert event["id"] == "evt_1"
    assert [call[0] for call in calls] == [
        "Customer.create",
        "checkout.Session.create",
        "billing_portal.Session.create",
        "Subscription.modify",
        "Subscription.cancel",
        "Subscription.modify",
        "Subscription.retrieve",
        "PaymentMethod.list",
        "PaymentMethod.detach",
        "Webhook.construct_event",
    ]
    checkout_call = next(call for call in calls if call[0] == "checkout.Session.create")
    assert checkout_call[2]["mode"] == "subscription"
    assert checkout_call[2]["client_reference_id"] == "u1"
    assert checkout_call[2]["subscription_data"]["metadata"]["nexa_user_id"] == "u1"


def test_stripe_provider_requires_webhook_signature_secret():
    provider = StripeBillingProvider(
        SimpleNamespace(
            stripe_secret_key="sk_test_fake",
            stripe_webhook_secret=None,
            stripe_price_starter_monthly=None,
            stripe_price_starter_yearly=None,
            stripe_price_pro_monthly=None,
            stripe_price_pro_yearly=None,
            stripe_price_business_monthly=None,
            stripe_price_business_yearly=None,
        )
    )
    assert provider.configured is False
