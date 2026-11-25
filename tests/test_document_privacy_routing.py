"""Tests for fail-closed routing when user document context is present."""
from __future__ import annotations

import pytest

from app.gateway.models import GatewayResult, TaskKind
from app.learning.document_privacy import document_routing_options, local_provider_is_safe
from app.learning.settings import LearningSettings


def test_document_context_forces_local_model_and_disables_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.learning.settings.get_learning_settings",
        lambda: LearningSettings(allow_cloud_on_documents=False),
    )

    options = document_routing_options(
        contains_document_context=True,
        model="gpt-4o",
        task_kind=TaskKind.REASONING,
    )

    assert options == {
        "model": "auto",
        "task_kind": TaskKind.LOCAL,
        "allow_fallback": False,
    }


def test_document_context_can_use_cloud_only_after_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(
        "app.learning.settings.get_learning_settings",
        lambda: LearningSettings(allow_cloud_on_documents=True),
    )

    options = document_routing_options(
        contains_document_context=True,
        model="gpt-4o",
        task_kind=TaskKind.REASONING,
    )

    assert options == {"model": "gpt-4o", "task_kind": TaskKind.REASONING}


def test_requests_without_document_context_keep_normal_routing(monkeypatch):
    monkeypatch.setattr(
        "app.learning.settings.get_learning_settings",
        lambda: LearningSettings(allow_cloud_on_documents=False),
    )

    options = document_routing_options(
        contains_document_context=False,
        model="gpt-4o",
        task_kind=TaskKind.SIMPLE,
    )

    assert options == {"model": "gpt-4o", "task_kind": TaskKind.SIMPLE}


def test_non_gateway_provider_must_be_local_for_document_context():
    assert local_provider_is_safe("ollama")
    assert local_provider_is_safe("mock")
    assert not local_provider_is_safe("openai")


@pytest.mark.asyncio
async def test_agent_document_context_uses_local_gateway(monkeypatch):
    from app.agent.agent import Agent
    from app.agent.models import AgentState, AgentTask, PlannedAction, PlannedActionType

    monkeypatch.setattr(
        "app.learning.settings.get_learning_settings",
        lambda: LearningSettings(allow_cloud_on_documents=False),
    )

    class FakeGateway:
        def __init__(self):
            self.kwargs = None

        async def chat(self, messages, **kwargs):
            self.kwargs = kwargs
            return GatewayResult(
                text="Summary",
                provider="ollama",
                model_id="local-test",
                display_name="Local test",
            )

    gateway = FakeGateway()
    agent = Agent(
        planner=None,
        tool_selector=None,
        executor=None,
        verifier=None,
        model_gateway=gateway,
    )
    state = AgentState(
        task=AgentTask(
            description="Summarize this document",
            context="PRIVATE DOCUMENT CONTENT",
            metadata={"contains_documents": True},
        )
    )
    action = PlannedAction(
        type=PlannedActionType.FINAL_ANSWER,
        final_answer="Draft",
    )

    result = await agent._maybe_ask_model(state, action)

    assert result.final_answer == "Summary"
    assert gateway.kwargs == {
        "model": "auto",
        "task_kind": TaskKind.LOCAL,
        "allow_fallback": False,
    }


@pytest.mark.asyncio
async def test_chat_endpoint_core_forces_local_for_attachments(monkeypatch):
    from app.config.settings import Settings
    from app.core.nexa_core import NexaCore
    from app.gateway.models import GatewayResult
    from app.models.chat import ChatMessage, ChatRequest, ChatRole

    monkeypatch.setattr(
        "app.learning.settings.get_learning_settings",
        lambda: LearningSettings(allow_cloud_on_documents=False),
    )

    class FakeProvider:
        name = "mock"
        model_name = "mock-model"

    class FakeGateway:
        def __init__(self):
            self.kwargs = None

        async def chat(self, messages, **kwargs):
            self.kwargs = kwargs
            return GatewayResult(
                text="Local summary",
                provider="ollama",
                model_id="local-model",
                display_name="Local model",
            )

    gateway = FakeGateway()
    core = NexaCore(FakeProvider(), Settings(_env_file=None), gateway=gateway)
    monkeypatch.setattr(
        core,
        "_resolve_attachments",
        lambda request: ([ChatMessage(role=ChatRole.SYSTEM, content="PRIVATE")], [], ["doc-1"], True),
    )
    monkeypatch.setattr(core, "_wants_live_web", lambda request: False)

    response = await core.chat(
        ChatRequest(message="Summarize", model="gpt-4o", attachment_ids=["doc-1"])
    )

    assert response.provider == "ollama"
    assert gateway.kwargs == {
        "model": "auto",
        "task_kind": TaskKind.LOCAL,
        "allow_fallback": False,
        "images": None,
    }


@pytest.mark.asyncio
async def test_chat_stream_core_forces_local_for_knowledge_context(monkeypatch):
    from app.config.settings import Settings
    from app.core.nexa_core import NexaCore
    from app.gateway.models import StreamEvent
    from app.knowledge.models import RetrievalResult, RetrievedChunk
    from app.models.chat import ChatRequest

    monkeypatch.setattr(
        "app.learning.settings.get_learning_settings",
        lambda: LearningSettings(allow_cloud_on_documents=False),
    )

    class FakeProvider:
        name = "mock"
        model_name = "mock-model"

    class FakeKnowledge:
        def search(self, *args, **kwargs):
            return RetrievalResult(chunks=[RetrievedChunk(chunk_id="c1", document_id="d1", filename="private.txt", source="upload", text="PRIVATE", score=1.0)], citations=[], context_text="PRIVATE", insufficient=False)

        def build_context_message(self, result):
            from app.models.chat import ChatMessage, ChatRole
            return "PRIVATE"

    class FakeGateway:
        def __init__(self):
            self.kwargs = None

        async def stream(self, messages, **kwargs):
            self.kwargs = kwargs
            yield StreamEvent(type="done", provider="ollama", model="local-model")

    gateway = FakeGateway()
    core = NexaCore(
        FakeProvider(),
        Settings(_env_file=None),
        gateway=gateway,
        knowledge_base=FakeKnowledge(),
    )
    events = [
        event
        async for event in core.stream_events(
            ChatRequest(message="Summarize my files", model="gpt-4o", use_knowledge_base=True)
        )
    ]

    assert events[-1].type == "done"
    assert gateway.kwargs["model"] == "auto"
    assert gateway.kwargs["task_kind"] == TaskKind.LOCAL
    assert gateway.kwargs["allow_fallback"] is False
