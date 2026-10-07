"""Tests for the ImageGenerationProvider interface and factory.
No real image generation happens in this part unless ``OPENAI_API_KEY`` +
``IMAGE_PROVIDER=openai`` are configured - by default NEXA reports clearly
that image generation is unavailable rather than fabricating an image.
"""
from __future__ import annotations
import pytest
from app.config.settings import Settings
from app.image_generation.base import ImageGenerationProvider
from app.image_generation.factory import ImageGenerationProviderFactory
from app.image_generation.not_configured import (
    NOT_CONFIGURED_MESSAGE,
    NotConfiguredImageGenerationProvider,
)
from app.models.errors import ProviderConfigurationError
def _settings(**overrides) -> Settings:
    defaults = dict(IMAGE_PROVIDER="none")
    defaults.update(overrides)
    return Settings(**defaults)
async def test_not_configured_provider_generate_reports_exact_message():
    provider = NotConfiguredImageGenerationProvider()
    with pytest.raises(ProviderConfigurationError) as exc_info:
        await provider.generate("a cat wearing sunglasses")
    assert exc_info.value.message == "Image generation provider is not configured."
    assert exc_info.value.message == NOT_CONFIGURED_MESSAGE
async def test_not_configured_provider_edit_reports_exact_message():
    provider = NotConfiguredImageGenerationProvider()
    with pytest.raises(ProviderConfigurationError) as exc_info:
        await provider.edit(image=b"fake-png-bytes", prompt="add a hat")
    assert exc_info.value.message == "Image generation provider is not configured."
async def test_not_configured_provider_health_check_is_false():
    assert await NotConfiguredImageGenerationProvider().health_check() is False
def test_image_generation_provider_is_abstract():
    with pytest.raises(TypeError):
        ImageGenerationProvider()
# --- Factory ---------------------------------------------------------------------
def test_factory_defaults_to_not_configured():
    provider = ImageGenerationProviderFactory.create(_settings())
    assert isinstance(provider, NotConfiguredImageGenerationProvider)
def test_factory_falls_back_to_not_configured_when_openai_key_missing():
    settings = _settings(IMAGE_PROVIDER="openai", OPENAI_API_KEY=None)
    provider = ImageGenerationProviderFactory.create(settings)
    assert isinstance(provider, NotConfiguredImageGenerationProvider)
def test_factory_builds_real_provider_when_openai_configured():
    settings = _settings(IMAGE_PROVIDER="openai", OPENAI_API_KEY="sk-test-key")
    provider = ImageGenerationProviderFactory.create(settings)
    assert provider.name == "openai"
async def test_factory_default_provider_never_fabricates_an_image():
    provider = ImageGenerationProviderFactory.create(_settings())
    with pytest.raises(ProviderConfigurationError):
        await provider.generate("anything")
