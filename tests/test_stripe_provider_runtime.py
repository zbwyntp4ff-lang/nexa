"""Contract tests for NEXA's Stripe 17 adapter without network requests."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from app.billing.plans import get_plan
from app.billing.stripe_provider import StripeBillingProvider
from app.config.settings import Settings


def test_stripe_adapter_checkout_portal_subscription_and_webhook(monkeypatch):
    calls = []

    def record(name):
        def call(*args, **kwargs):
            calls.append((name, args, kwargs))
            return {"id": f"{name}_test", "url": "https://stripe.test/session"}
        return call

    fake = SimpleNamespace(
        api_key=None,
        Customer=SimpleNamespace(create=record("customer.create")),
        checkout=SimpleNamespace(Session=SimpleNamespace(create=record("checkout.create"))),
        billing_portal=SimpleNamespace(Session=SimpleNamespace(create=record("portal.create"))),
        Subscription=SimpleNamespace(
            modify=record("subscription.modify"),
            cancel=record("subscription.cancel"),
            retrieve=record("subscription.retrieve"),
        ),
        PaymentMethod=SimpleNamespace(
            list=record("payment_method.list"),
            detach=record("payment_method.detach"),
        ),
        Webhook=SimpleNamespace(construct_event=record("webhook.construct_event")),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake)
    settings = Settings(
        _env_file=None,
        STRIPE_SECRET_KEY="sk_test_contract",
        STRIPE_WEBHOOK_SECRET="whsec_test_contract",
        STRIPE_PRICE_PRO_MONTHLY="price_pro_month",
    )
    provider = StripeBillingProvider(settings)

    customer = provider.create_customer(email="user@example.com", name="Test", user_id="u1")
    assert customer["id"] == "customer.create_test"
    assert fake.api_key == "sk_test_contract"

    checkout = provider.create_checkout_session(
        customer_id="cus_test",
        plan=get_plan("pro"),
        interval="month",
        success_url="https://app.test/success",
        cancel_url="https://app.test/cancel",
        user_id="u1",
    )
    checkout_call = next(c for c in calls if c[0] == "checkout.create")
    checkout_args = checkout_call[2]
    assert checkout_args["mode"] == "subscription"
    assert checkout_args["line_items"] == [{"price": "price_pro_month", "quantity": 1}]
    assert checkout_args["subscription_data"]["metadata"]["nexa_user_id"] == "u1"
    assert checkout["id"] == "checkout.create_test"

    provider.create_portal_session(customer_id="cus_test", return_url="https://app.test/account")
    provider.cancel_subscription("sub_test", at_period_end=True)
    provider.resume_subscription("sub_test")
    provider.retrieve_subscription("sub_test")
    provider.list_payment_methods("cus_test")
    provider.detach_payment_method("pm_test")
    event = provider.construct_event(b'{"id":"evt_test"}', "sig_test")
    assert event["id"] == "webhook.construct_event_test"

    assert {name for name, _, _ in calls} == {
        "customer.create",
        "checkout.create",
        "portal.create",
        "subscription.modify",
        "subscription.retrieve",
        "payment_method.list",
        "payment_method.detach",
        "webhook.construct_event",
    }
    assert next(c for c in calls if c[0] == "webhook.construct_event")[1] == (
        b'{"id":"evt_test"}', "sig_test", "whsec_test_contract"
    )


def test_stripe_adapter_uses_inline_price_when_price_id_missing(monkeypatch):
    captured = {}
    fake = SimpleNamespace(
        api_key=None,
        checkout=SimpleNamespace(
            Session=SimpleNamespace(create=lambda **kwargs: captured.update(kwargs) or {"id": "cs_inline"})
        ),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake)
    provider = StripeBillingProvider(
        Settings(_env_file=None, STRIPE_SECRET_KEY="sk_test_contract")
    )
    provider.create_checkout_session(
        customer_id="cus_test",
        plan=get_plan("starter"),
        interval="month",
        success_url="https://app.test/success",
        cancel_url="https://app.test/cancel",
        user_id="u2",
    )
    item = captured["line_items"][0]
    assert item["price_data"]["currency"] == get_plan("starter").currency
    assert item["price_data"]["recurring"]["interval"] == "month"
    assert item["price_data"]["product_data"]["metadata"]["nexa_plan"] == "starter"
