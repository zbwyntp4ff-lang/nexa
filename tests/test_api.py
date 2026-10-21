"""Tests for the HTTP API surface.
Uses FastAPI's TestClient (sync wrapper over httpx) so no real server or
network access is needed. The provider dependency is overridden with an
in-memory ``NexaCore``/``MockProvider`` pair so no external API is ever
called.
"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.api.deps import get_nexa_core
from app.config.settings import Settings
from app.core.nexa_core import NexaCore
from app.main import app
from app.providers.base import AIProvider
from app.providers.mock import MockProvider
def _test_settings(**overrides) -> Settings:
    defaults = dict(AI_PROVIDER="mock", MAX_MESSAGE_LENGTH=50, REQUEST_TIMEOUT_SECONDS=1.0)
    defaults.update(overrides)
    return Settings(**defaults)
@pytest.fixture
def client():
    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=MockProvider(), settings=_test_settings()
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["version"]
    assert body["storage_mode"] in ("persistent", "ephemeral")
    assert "database_ok" in body
    assert body.get("ollama_required") is False
def test_status_endpoint(client: TestClient):
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == "mock"
    assert body["provider_healthy"] is True
def test_model_endpoint(client: TestClient):
    response = client.get("/api/v1/model")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["model"]
def test_chat_endpoint_happy_path(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": "Привет, NEXA!"})
    assert response.status_code == 200
    body = response.json()
    assert "Привет, NEXA!" in body["message"]
    assert body["provider"] == "mock"
    assert "latency_ms" in body
def test_chat_endpoint_rejects_empty_message(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "EmptyMessageError"
    assert "stack" not in body["message"].lower()
def test_chat_endpoint_rejects_whitespace_message(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": "   "})
    assert response.status_code == 400
    assert response.json()["error"] == "EmptyMessageError"
def test_chat_endpoint_rejects_too_long_message(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": "x" * 51})
    assert response.status_code == 400
    assert response.json()["error"] == "MessageTooLongError"
def test_chat_endpoint_missing_message_field_returns_422(client: TestClient):
    response = client.post("/api/v1/chat", json={})
    assert response.status_code == 422
def test_chat_endpoint_provider_error_returns_502_without_stack_trace(client: TestClient):
    class _BrokenProvider(AIProvider):
        name = "broken"
        @property
        def model_name(self) -> str:
            return "broken-model"
        async def generate(self, messages):
            raise RuntimeError("some internal SDK detail that must not leak")
        async def stream(self, messages):
            raise RuntimeError("boom")
            yield  # pragma: no cover
        async def health_check(self) -> bool:
            return False
    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=_BrokenProvider(), settings=_test_settings()
    )
    response = client.post("/api/v1/chat", json={"message": "hello"})
    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "ModelError"
    assert "Traceback" not in body["message"]
def test_chat_endpoint_timeout_returns_504(client: TestClient):
    class _SlowProvider(AIProvider):
        name = "slow"
        @property
        def model_name(self) -> str:
            return "slow-model"
        async def generate(self, messages):
            import asyncio
            await asyncio.sleep(5)
            return "too late"
        async def stream(self, messages):
            yield "too late"
        async def health_check(self) -> bool:
            return True
    app.dependency_overrides[get_nexa_core] = lambda: NexaCore(
        provider=_SlowProvider(), settings=_test_settings(REQUEST_TIMEOUT_SECONDS=0.05)
    )
    response = client.post("/api/v1/chat", json={"message": "hello"})
    assert response.status_code == 504
    assert response.json()["error"] == "ProviderTimeoutError"
def test_unhandled_exception_returns_generic_500_without_details(client: TestClient):
    class _CrashingCore:
        async def chat(self, request):
            raise ValueError("very sensitive internal detail")
        async def health_check(self):
            return True
        @property
        def provider(self):
            raise RuntimeError("should not be reached")
    app.dependency_overrides[get_nexa_core] = lambda: _CrashingCore()
    with TestClient(app, raise_server_exceptions=False) as unsafe_client:
        response = unsafe_client.post("/api/v1/chat", json={"message": "hello"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "InternalServerError"
    assert "very sensitive internal detail" not in body["message"]
