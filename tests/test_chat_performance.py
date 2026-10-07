"""Chat stays on the short path: one model call, no research, real streaming."""
from __future__ import annotations
from collections.abc import AsyncIterator
import pytest
from fastapi.testclient import TestClient
from app.api.deps import get_nexa_core
from app.config.settings import Settings
from app.core.nexa_core import NexaCore
from app.main import app
from app.models.chat import ChatMessage, ChatRequest
from app.models.errors import ProviderTimeoutError
from app.providers.base import AIProvider
from app.providers.local_provider import LocalProvider
from app.web.research_tool import ResearchTool
class CountingProvider(AIProvider):
    name = "counting"
    def __init__(self) -> None:
        self.calls = 0
        self.stream_calls = 0
    @property
    def model_name(self) -> str:
        return "counting-model"
    async def generate(self, messages: list[ChatMessage]) -> str:
        self.calls += 1
        return "925"
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.stream_calls += 1
        yield "25 * 37"
        yield " = 925"
    async def health_check(self) -> bool:
        return True
class TimeoutProvider(AIProvider):
    name = "timeout"
    @property
    def model_name(self) -> str:
        return "timeout-model"
    async def generate(self, messages: list[ChatMessage]) -> str:
        raise ProviderTimeoutError()
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        raise ProviderTimeoutError()
        yield ""  # pragma: no cover
    async def health_check(self) -> bool:
        return False
def test_ollama_payload_keeps_the_model_loaded():
    provider = LocalProvider("http://127.0.0.1:11434", model="llama3")
    payload = provider._to_payload([ChatMessage(role="user", content="25 * 37")], stream=True)
    assert payload["keep_alive"] == "30m"
    assert payload["stream"] is True
    assert payload["model"] == "llama3"
@pytest.mark.asyncio
async def test_plain_chat_calls_the_model_once_and_skips_research(monkeypatch):
    async def explode(self, **kwargs):
        raise AssertionError("Web Research must not run for a plain chat message")
    monkeypatch.setattr(ResearchTool, "execute", explode)
    provider = CountingProvider()
    core = NexaCore(provider=provider, settings=Settings(AI_PROVIDER="mock", REQUEST_TIMEOUT_SECONDS=2.0))
    response = await core.chat(ChatRequest(message="25 * 37"))
    assert response.message == "925"
    assert provider.calls == 1
    events = [event async for event in core.stream_events(ChatRequest(message="25 * 37"))]
    assert provider.stream_calls == 1
    assert [event.text for event in events if event.type == "delta"] == ["25 * 37", " = 925"]
    assert events[-1].type == "done"
def test_chat_stream_endpoint_completes_and_timeout_is_reported():
    provider = CountingProvider()
    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=provider, settings=Settings(AI_PROVIDER="mock", REQUEST_TIMEOUT_SECONDS=1.0)
    )
    try:
        client = TestClient(app)
        response = client.post("/api/v1/chat/stream", json={"message": "25 * 37"})
        assert response.status_code == 200
        body = response.text
        assert "25 * 37" in body
        assert " = 925" in body
        assert '"type":"done"' in body or '"type": "done"' in body
        assert provider.calls == 0
        assert provider.stream_calls == 1
    finally:
        app.dependency_overrides.clear()
    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=TimeoutProvider(), settings=Settings(AI_PROVIDER="mock", REQUEST_TIMEOUT_SECONDS=1.0)
    )
    try:
        client = TestClient(app)
        blocked = client.post("/api/v1/chat", json={"message": "25 * 37"})
        assert blocked.status_code == 504
    finally:
        app.dependency_overrides.clear()
