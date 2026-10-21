"""Phase 6 beta readiness regressions."""
from __future__ import annotations

import pytest

from app.agent.compound import (
    DeliverableKind,
    build_compound_plan,
    tool_input_for,
)
from app.agent.models import AgentState, AgentStatus, AgentStep, AgentStepType, AgentTask
from app.knowledge.eval_rag import DEFAULT_CASES, DEFAULT_CORPUS, evaluate_retrievers
from app.learning.beta_cases import BETA_CASES


def test_beta_cases_cover_ru_en_minimum():
    ru = [c for c in BETA_CASES if c["lang"] == "ru"]
    en = [c for c in BETA_CASES if c["lang"] == "en"]
    assert len(ru) >= 30
    assert len(en) >= 5
    cats = {c["category"] for c in BETA_CASES}
    for needed in (
        "general_knowledge",
        "math",
        "programming",
        "comparison",
        "multi_step",
        "ambiguous",
        "missing_data",
    ):
        assert needed in cats


def test_comparison_task_uses_comparison_sheet_not_financial_model():
    task = (
        "Исследуй пять AI-ассистентов, сравни их возможности, ограничения и модели монетизации. "
        "Подготовь сравнительную таблицу в Excel, презентацию на 10 слайдов и подробный Word-отчёт. "
        "Сохрани результаты в папку одного проекта"
    )
    plan = build_compound_plan(task)
    kinds = [d.kind.value for d in plan.deliverables]
    assert "research" in kinds
    assert "spreadsheet" in kinds
    assert "presentation" in kinds
    assert "document" in kinds
    assert "project_folder" in kinds

    state = AgentState(task=AgentTask(description=task), status=AgentStatus.RUNNING)
    state.steps.append(
        AgentStep(
            index=0,
            step_type=AgentStepType.TOOL_CALL,
            tool_name="web_research",
            success=True,
            output={
                "sources": [
                    {
                        "title": "Compare",
                        "url": "https://example.com/a",
                        "text": "ChatGPT Claude Gemini Copilot pricing subscription API limits",
                        "content_hash": "h1",
                    }
                ],
                "results": [],
            },
        )
    )
    sheet = next(d for d in plan.deliverables if d.kind == DeliverableKind.SPREADSHEET)
    payload = tool_input_for(sheet, plan, state)
    assert payload.get("financial_model") is not True
    assert payload.get("rows")
    assert payload["rows"][0][0] == "Assistant"
    assert any(r[0] == "ChatGPT" for r in payload["rows"][1:])


def test_financial_model_still_used_for_budget_tasks():
    plan = build_compound_plan("Составь финансовую модель unit economics в Excel")
    state = AgentState(
        task=AgentTask(description=plan.goal),
        status=AgentStatus.RUNNING,
    )
    sheet = next(d for d in plan.deliverables if d.kind == DeliverableKind.SPREADSHEET)
    payload = tool_input_for(sheet, plan, state)
    assert payload.get("financial_model") is True


def test_rag_beta_corpus_expanded():
    assert len(DEFAULT_CORPUS) >= 10
    assert len(DEFAULT_CASES) >= 12
    report = evaluate_retrievers()
    assert report["methods"]["hashing256"]["recall_at_k"] is not None
    assert report["methods"]["hashing512"]["mrr"] is not None
    assert report["methods"]["token_overlap"]["latency_ms_avg"] is not None


def test_result_store_acl_under_tokens_enforce(tmp_path, monkeypatch):
    """P0: ownerless or cross-user results must not leak when TOKENS_ENFORCE."""
    from app.config.settings import get_settings
    from app.tools.office.result_store import ResultStore

    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    get_settings.cache_clear()
    store = ResultStore(tmp_path)
    owned = store.save_bytes(
        b"PK\x03\x04owned",
        filename="a.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        extension="pptx",
        task_id="t1",
        tool_name="create_presentation",
        user_id="user-a",
    )
    orphan = store.save_bytes(
        b"PK\x03\x04orphan",
        filename="b.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        extension="pptx",
        task_id="t2",
        tool_name="create_presentation",
        user_id=None,
    )
    assert store.get(owned.file_id, user_id="user-a") is not None
    assert store.get(owned.file_id, user_id="user-b") is None
    assert store.get(owned.file_id, user_id=None) is None
    assert store.get(orphan.file_id, user_id="user-a") is None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_agent_injects_user_id_into_office_tools(tmp_path, monkeypatch):
    from app.agent.agent import Agent
    from app.agent.executor import Executor
    from app.agent.models import AgentTask
    from app.agent.planner import RuleBasedPlanner
    from app.agent.tool_selector import ToolSelector
    from app.agent.verifier import Verifier
    from app.config.settings import get_settings
    from app.tools.office.document import DocumentTool
    from app.tools.office.result_store import ResultStore
    from app.tools.registry import ToolRegistry

    monkeypatch.setenv("TOKENS_ENFORCE", "true")
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path))
    get_settings.cache_clear()
    store = ResultStore(tmp_path)
    registry = ToolRegistry()
    registry.register(DocumentTool(store))
    registry._result_store = store  # type: ignore[attr-defined]
    agent = Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        max_steps=6,
        timeout_seconds=60,
        error_limit=4,
    )
    result = await agent.run(
        AgentTask(
            description="Создай Word-отчёт про тест ACL",
            metadata={"user_id": "owner-42"},
        )
    )
    assert result.status.value == "completed" or result.final_answer
    # Find saved file with owner
    owned = [r for r in store._index.values() if r.user_id == "owner-42"]
    assert owned, "office tool must persist user_id from task metadata"
    get_settings.cache_clear()
