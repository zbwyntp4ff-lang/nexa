"""Thin Stripe SDK wrapper — never stores card numbers/CVV."""
from __future__ import annotations

from typing import Any

from app.billing.errors import BillingNotConfiguredError
from app.billing.plans import BillingInterval, PlanDefinition, price_for
from app.config.settings import Settings


class StripeBillingProvider:
    """Official Stripe SDK adapter for Checkout, Portal, and Webhooks."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stripe = None

    @property
    def configured(self) -> bool:
        return bool(self._settings.stripe_secret_key and self._settings.stripe_webhook_secret)

    def _client(self):
        if self._stripe is None:
            if not self._settings.stripe_secret_key:
                raise BillingNotConfiguredError()
            try:
                import stripe
            except ImportError as exc:  # pragma: no cover
                raise BillingNotConfiguredError(
                    "The 'stripe' package is required. Install it from requirements.txt."
                ) from exc
            stripe.api_key = self._settings.stripe_secret_key
            self._stripe = stripe
        return self._stripe

    def create_customer(self, *, email: str, name: str, user_id: str) -> Any:
        stripe = self._client()
        return stripe.Customer.create(
            email=email,
            name=name,
            metadata={"nexa_user_id": user_id},
        )

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        plan: PlanDefinition,
        interval: BillingInterval,
        success_url: str,
        cancel_url: str,
        user_id: str,
    ) -> Any:
        stripe = self._client()
        amount = price_for(plan.id, interval)
        if amount < 0:
            raise BillingNotConfiguredError("Enterprise plans are not checkout-purchasable.")
        if amount == 0:
            raise BillingNotConfiguredError("Free plan does not require checkout.")

        price_id = self._price_id_for(plan.id, interval)
        if price_id:
            line_items = [{"price": price_id, "quantity": 1}]
        else:
            line_items = [
                {
                    "price_data": {
                        "currency": plan.currency,
                        "unit_amount": amount,
                        "recurring": {"interval": "year" if interval == "year" else "month"},
                        "product_data": {
                            "name": f"NEXA {plan.name}",
                            "metadata": {"nexa_plan": plan.id},
                        },
                    },
                    "quantity": 1,
                }
            ]

        return stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=user_id,
            allow_promotion_codes=True,
            billing_address_collection="auto",
            payment_method_types=["card"],
            # Apple Pay / Google Pay appear automatically via Stripe Checkout
            # when enabled in the Stripe Dashboard for the account/country.
            subscription_data={
                "metadata": {
                    "nexa_user_id": user_id,
                    "nexa_plan": plan.id,
                    "nexa_interval": interval,
                }
            },
            metadata={
                "nexa_user_id": user_id,
                "nexa_plan": plan.id,
                "nexa_interval": interval,
            },
        )

    def create_portal_session(self, *, customer_id: str, return_url: str) -> Any:
        stripe = self._client()
        return stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

    def cancel_subscription(self, provider_subscription_id: str, *, at_period_end: bool = True) -> Any:
        stripe = self._client()
        if at_period_end:
            return stripe.Subscription.modify(provider_subscription_id, cancel_at_period_end=True)
        return stripe.Subscription.cancel(provider_subscription_id)

    def resume_subscription(self, provider_subscription_id: str) -> Any:
        stripe = self._client()
        return stripe.Subscription.modify(provider_subscription_id, cancel_at_period_end=False)

    def retrieve_subscription(self, provider_subscription_id: str) -> Any:
        stripe = self._client()
        return stripe.Subscription.retrieve(provider_subscription_id)

    def list_payment_methods(self, customer_id: str) -> list[Any]:
        stripe = self._client()
        result = stripe.PaymentMethod.list(customer=customer_id, type="card")
        return list(result.data)

    def detach_payment_method(self, payment_method_id: str) -> Any:
        stripe = self._client()
        return stripe.PaymentMethod.detach(payment_method_id)

    def construct_event(self, payload: bytes, signature: str) -> Any:
        stripe = self._client()
        secret = self._settings.stripe_webhook_secret
        if not secret:
            raise BillingNotConfiguredError("STRIPE_WEBHOOK_SECRET is not set.")
        return stripe.Webhook.construct_event(payload, signature, secret)

    def _price_id_for(self, plan_id: str, interval: BillingInterval) -> str | None:
        s = self._settings
        mapping = {
            ("starter", "month"): s.stripe_price_starter_monthly,
            ("starter", "year"): s.stripe_price_starter_yearly,
            ("pro", "month"): s.stripe_price_pro_monthly,
            ("pro", "year"): s.stripe_price_pro_yearly,
            ("business", "month"): s.stripe_price_business_monthly,
            ("business", "year"): s.stripe_price_business_yearly,
        }
        value = mapping.get((plan_id, interval))
        return value.strip() if value else None
