"""Billing domain errors."""
from __future__ import annotations

from app.models.errors import NexaError


class BillingError(NexaError):
    default_code = "BillingError"
    default_message = "Billing request failed."


class BillingNotConfiguredError(BillingError):
    default_code = "BillingNotConfigured"
    default_message = "Payment provider is not configured. Set Stripe keys in the environment."


class InvalidBillingReturnUrlError(BillingError):
    default_code = "InvalidBillingReturnUrl"
    default_message = "Billing return URLs must use the configured application origin."


class PlanNotPurchasableError(BillingError):
    default_code = "PlanNotPurchasable"
    default_message = "This plan cannot be purchased online."


class EntitlementDeniedError(BillingError):
    default_code = "EntitlementDenied"
    default_message = "Your current plan does not include this feature."


class UsageLimitExceededError(BillingError):
    default_code = "UsageLimitExceeded"
    default_message = "You have reached the usage limit for your plan."


class WebhookSignatureError(BillingError):
    default_code = "WebhookSignatureInvalid"
    default_message = "Webhook signature verification failed."


class RateLimitedError(BillingError):
    default_code = "RateLimited"
    default_message = "Too many billing requests. Try again shortly."
