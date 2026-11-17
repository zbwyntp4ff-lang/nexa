"""Answer quality / RAG / search plumbing — no paid APIs required."""
from __future__ import annotations

import pytest

from app.core.nexa_core import NexaCore, _FAST_SYSTEM_PROMPT
from app.knowledge.knowledge_base import KNOWLEDGE_INSUFFICIENT_NOTE, KnowledgeBase
from app.knowledge.models import RetrievalResult
from app.knowledge.retriever import _token_overlap
from app.knowledge_core.composer import KnowledgeCoreComposer
from app.knowledge_core.store import reload_packs
from app.models.chat import ChatMessage, ChatRequest, ChatRole
from app.providers.mock import MockProvider
from app.web.duckduckgo_provider import unwrap_ddg_url


def test_fast_prompt_forbids_echo_and_invented_sources():
    lower = _FAST_SYSTEM_PROMPT.lower()
    assert "echo" in lower
    assert "invent" in lower
    assert "lead with" in lower or "direct answer" in lower


def test_knowledge_core_packs_load_and_always_quality():
    packs = reload_packs()
    assert packs, "expected JSON packs under data/knowledge_core/packs"
    ids = {p.id for p in packs}
    assert "quality_always" in ids
    assert "education" in ids
    result = KnowledgeCoreComposer(packs).compose("Привет, как дела?")
    assert "quality_always" in result.pack_ids or "response_quality" in result.pack_ids
    assert result.text
    assert "invent" in result.text.lower() or "не выдумывай" in result.text.lower() or "FACT" in result.text or "echo" in result.text.lower()


def test_education_pack_triggers_on_ege():
    packs = reload_packs()
    result = KnowledgeCoreComposer(packs).compose("Помоги подготовиться к ЕГЭ по математике")
    assert "education" in result.pack_ids
    assert result.pack_ids.count("education") == 1


def test_ddg_unwrap_uddg():
    raw = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpath&rut=abc"
    assert unwrap_ddg_url(raw) == "https://example.com/path"
    assert unwrap_ddg_url("/l/?uddg=https%3A%2F%2Fnews.example%2Fa") == "https://news.example/a"
    assert unwrap_ddg_url("not-a-url") is None


def test_token_overlap_filters_unrelated():
    assert _token_overlap("python fastapi docker", "python and fastapi tutorial") >= 1
    assert _token_overlap("zebra pineapple", "quantum chromodynamics lecture") == 0


@pytest.mark.asyncio
async def test_rag_miss_does_not_poison_chat_messages(tmp_path, monkeypatch):
    """Auto-RAG miss must not inject KNOWLEDGE_INSUFFICIENT_NOTE into chat."""
    from app.config.settings import Settings

    settings = Settings(
        _env_file=None,
        AI_PROVIDER="mock",
        KNOWLEDGE_STORE_PATH=str(tmp_path / "kv.json"),
        KNOWLEDGE_DOCUMENTS_PATH=str(tmp_path / "kd.json"),
    )
    from app.knowledge.knowledge_base import build_knowledge_base

    kb = build_knowledge_base(settings)
    core = NexaCore(provider=MockProvider(), settings=settings, knowledge_base=kb)
    request = ChatRequest(message="What is 2+2?", use_knowledge_base=True)
    msgs, result = core._resolve_knowledge(request)
    assert msgs == []
    assert result is not None
    assert result.insufficient is True
    # ensure the poison string is not used as chat system text
    assert not any(KNOWLEDGE_INSUFFICIENT_NOTE in (m.content or "") for m in msgs)


@pytest.mark.asyncio
async def test_research_chat_does_not_overwrite_nexa_core(monkeypatch):
    """Regression: compose result must not replace NexaCore (was 500)."""
    from app.api.routes import research as research_routes
    from app.gateway.models import GatewayResult
    from app.tools.base import ToolResult

    class _FakeGateway:
        async def chat(self, messages, model=None, task_kind=None, images=None):
            return GatewayResult(
                text="Cited answer [1]",
                provider="mock",
                model_id="nexa-mock-1",
                display_name="Mock",
            )

    class _FakeCore:
        gateway = _FakeGateway()

    class _FakeTool:
        async def execute(self, **kwargs):
            return ToolResult(
                success=True,
                output={
                    "query": kwargs.get("query"),
                    "results": [{"title": "T", "url": "https://example.com", "snippet": "s"}],
                    "sources": [
                        {
                            "url": "https://example.com",
                            "title": "Example",
                            "text": "Example body",
                            "content_hash": "abc",
                        }
                    ],
                },
            )

    class _FakeRegistry:
        def get(self, name):
            assert name == "web_research"
            return _FakeTool()

    monkeypatch.setattr(research_routes, "get_default_tool_registry", lambda: _FakeRegistry())

    resp = await research_routes.research_chat(
        research_routes.ResearchChatRequest(message="What is example.com?"),
        core=_FakeCore(),  # type: ignore[arg-type]
    )
    assert "Cited" in resp.message or resp.message
    assert resp.sources and resp.sources[0].url.startswith("https://")
