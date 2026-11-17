"""Regression tests for system-prompt and Knowledge Core composition."""
from app.config.settings import Settings
from app.core.nexa_core import NexaCore
from app.models.chat import ChatMessage, ChatRequest, ChatRole
from app.providers.mock import MockProvider


def test_custom_system_prompt_still_composes_knowledge_core() -> None:
    core = NexaCore(
        provider=MockProvider(),
        settings=Settings(AI_PROVIDER="mock"),
    )
    request = ChatRequest(
        message="Помоги написать программу на Python",
        task="coding",
        history=[
            ChatMessage(role=ChatRole.SYSTEM, content="Use the supplied coding rules."),
            ChatMessage(role=ChatRole.USER, content="Previous user message"),
        ],
    )

    messages = core._build_messages(request)

    assert messages[0].role == ChatRole.SYSTEM
    assert "Use the supplied coding rules." in messages[0].content
    assert any(
        item.role == ChatRole.USER and item.content == "Previous user message"
        for item in messages
    )
    assert messages[-1].role == ChatRole.USER
    assert messages[-1].content == request.message
