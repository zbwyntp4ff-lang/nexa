"""Behavioral tests for all OpenAI adapters using an in-memory fake SDK.

These tests exercise text, streaming, vision, image generation and image edit
without making network calls or requiring real provider credentials.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import openai

from app.image_generation.openai_provider import OpenAIImageGenerationProvider
from app.models.chat import ChatMessage, ChatRole, ImageAttachment
from app.providers.openai_provider import OpenAIProvider
from app.vision.openai_provider import OpenAIVisionProvider


class _FakeStream:
    def __aiter__(self):
        async def chunks():
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))])
        return chunks()


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return _FakeStream()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="mock completion"))]
        )


class _FakeImages:
    def __init__(self):
        self.generate_calls = []
        self.edit_calls = []

    async def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(url="https://example.test/generated.png", b64_json=None)])

    async def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(url="https://example.test/edited.png", b64_json=None)])


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())
        self.images = _FakeImages()
        self.models = SimpleNamespace(list=self._models_list)

    async def _models_list(self):
        return SimpleNamespace(data=[])


@pytest.fixture
def fake_sdk(monkeypatch):
    clients = []

    def factory(**kwargs):
        client = _FakeClient()
        clients.append((kwargs, client))
        return client

    monkeypatch.setattr(openai, "AsyncOpenAI", factory)
    return clients


@pytest.mark.asyncio
async def test_text_provider_sends_text_and_image_content_and_streams(fake_sdk):
    provider = OpenAIProvider(api_key="sk-test-not-real")
    messages = [
        ChatMessage(
            role=ChatRole.USER,
            content="Describe this",
            images=[ImageAttachment(data_base64="aGVsbG8=", mime_type="image/png")],
        )
    ]

    assert await provider.generate(messages) == "mock completion"
    chunks = [chunk async for chunk in provider.stream(messages)]
    assert chunks == ["hello", " world"]

    client = fake_sdk[0][1]
    payload = client.chat.completions.calls[0]["messages"][0]["content"]
    assert payload[0] == {"type": "text", "text": "Describe this"}
    assert payload[1]["image_url"]["url"] == "data:image/png;base64,aGVsbG8="
    assert client.chat.completions.calls[1]["stream"] is True


@pytest.mark.asyncio
async def test_vision_provider_sends_data_uri_and_returns_description(fake_sdk):
    provider = OpenAIVisionProvider(api_key="sk-test-not-real")
    result = await provider.analyze(b"png-bytes", "image/png", "Read the image")

    assert result.description == "mock completion"
    assert result.provider == "openai"
    request = fake_sdk[0][1].chat.completions.calls[0]
    content = request["messages"][0]["content"]
    assert content[0]["text"] == "Read the image"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_image_provider_generate_and_edit(fake_sdk):
    provider = OpenAIImageGenerationProvider(api_key="sk-test-not-real")
    generated = await provider.generate("a blue geometric logo", size="1024x1024", n=1)
    edited = await provider.edit(b"png-bytes", "remove the background", mask=b"mask-bytes")

    assert generated.images == ["https://example.test/generated.png"]
    assert generated.format == "url"
    assert edited.images == ["https://example.test/edited.png"]
    client = fake_sdk[0][1]
    assert client.images.generate_calls[0]["prompt"] == "a blue geometric logo"
    assert client.images.generate_calls[0]["size"] == "1024x1024"
    assert client.images.edit_calls[0]["image"] == b"png-bytes"
    assert client.images.edit_calls[0]["mask"] == b"mask-bytes"
