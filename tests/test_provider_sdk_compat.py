"""Runtime API-surface checks for the pinned provider SDKs.

These tests never contact OpenAI or Stripe. They verify that the exact SDK
versions installed by CI expose every API method used by NEXA adapters.
"""
from __future__ import annotations

import asyncio

from openai import AsyncOpenAI
import stripe

from app.billing.stripe_provider import StripeBillingProvider
from app.config.settings import Settings
from app.image_generation.openai_provider import OpenAIImageGenerationProvider
from app.providers.openai_provider import OpenAIProvider
from app.vision.openai_provider import OpenAIVisionProvider


def test_openai_sdk_exposes_all_methods_used_by_nexa() -> None:
    client = AsyncOpenAI(api_key="sk-test-not-a-real-key")
    try:
        assert callable(client.chat.completions.create)
        assert callable(client.images.generate)
        assert callable(client.images.edit)
        assert callable(client.models.list)
    finally:
        asyncio.run(client.close())


def test_nexa_openai_adapters_construct_with_pinned_sdk() -> None:
    text = OpenAIProvider(api_key="sk-test-not-a-real-key")
    vision = OpenAIVisionProvider(api_key="sk-test-not-a-real-key")
    image = OpenAIImageGenerationProvider(api_key="sk-test-not-a-real-key")
    assert text.model_name
    assert vision._model
    assert image._model
    asyncio.run(text._client.close())
    asyncio.run(vision._client.close())
    asyncio.run(image._client.close())


def test_stripe_sdk_exposes_all_methods_used_by_nexa() -> None:
    provider = StripeBillingProvider(
        Settings(
            _env_file=None,
            stripe_secret_key="sk_test_not_a_real_key",
            stripe_webhook_secret="whsec_test_not_a_real_secret",
        )
    )
    sdk = provider._client()
    assert callable(sdk.Customer.create)
    assert callable(sdk.checkout.Session.create)
    assert callable(sdk.billing_portal.Session.create)
    assert callable(sdk.Subscription.modify)
    assert callable(sdk.Subscription.cancel)
    assert callable(sdk.Subscription.retrieve)
    assert callable(sdk.PaymentMethod.list)
    assert callable(sdk.PaymentMethod.detach)
    assert callable(sdk.Webhook.construct_event)
