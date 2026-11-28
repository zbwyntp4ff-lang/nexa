"""Real PPTX/DOCX/XLSX/PDF creation — no external API keys."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.models import AgentState, AgentStep, AgentStepType, AgentTask, PlannedActionType
from app.agent.planner import RuleBasedPlanner
from app.tools.office.analysis import FileAnalysisTool
from app.tools.office.document import DocumentTool, verify_docx_bytes
from app.tools.office.pdf import PDFTool, verify_pdf_bytes
from app.tools.office.presentation import PresentationTool, verify_pptx_bytes
from app.tools.office.result_store import ResultStore
from app.tools.office.spreadsheet import SpreadsheetTool, verify_xlsx_bytes
from app.tools.registry import build_default_registry, get_default_tool_registry


@pytest.fixture
def store(tmp_path: Path) -> ResultStore:
    return ResultStore(tmp_path)


@pytest.mark.asyncio
async def test_presentation_creates_valid_pptx(store: ResultStore):
    tool = PresentationTool(store)
    result = await tool.execute(
        title="Market Plan",
        slides=[
            {"title": "Goals", "bullets": ["Grow ARR", "Cut churn"]},
            {"title": "Channels", "bullets": ["SEO", "Partners"]},
        ],
        filename="market_plan",
    )
    assert result.success, result.error
    assert result.output["download_url"].startswith("/api/v1/results/")
    assert "\\" not in result.output["download_url"]
    assert ":\\" not in str(result.output)
    path = store.absolute_path(result.output["file_id"])
    assert path is not None and path.is_file()
    info = verify_pptx_bytes(path.read_bytes())
    assert info["slide_count"] >= 3  # title + 2 content
    assert any("Market Plan" in t or "Goals" in t for t in info["titles"])


@pytest.mark.asyncio
async def test_presentation_rejects_empty_input(store: ResultStore):
    tool = PresentationTool(store)
    result = await tool.execute()
    assert not result.success
    assert "Provide" in (result.error or "")


@pytest.mark.asyncio
async def test_docx_creates_valid_document(store: ResultStore):
    tool = DocumentTool(store)
    result = await tool.execute(
        title="Weekly Report",
        sections=[{"title": "Status", "bullets": ["Shipped Phase 2", "Tests green"]}],
    )
    assert result.success, result.error
    path = store.absolute_path(result.output["file_id"])
    assert path and path.suffix == ".docx"
    info = verify_docx_bytes(path.read_bytes())
    assert info["paragraph_count"] >= 2
    assert any("Weekly Report" in t or "Status" in t for t in info["texts"])


@pytest.mark.asyncio
async def test_xlsx_creates_valid_workbook(store: ResultStore):
    tool = SpreadsheetTool(store)
    result = await tool.execute(
        title="Budget",
        rows=[["Item", "Amount"], ["Rent", "1000"], ["Tools", "200"]],
    )
    assert result.success, result.error
    path = store.absolute_path(result.output["file_id"])
    info = verify_xlsx_bytes(path.read_bytes())
    assert info["row_count"] == 3
    assert info["rows"][0][0] == "Item"
    assert info["rows"][1][1] == "1000"


@pytest.mark.asyncio
async def test_xlsx_rejects_empty_input(store: ResultStore):
    tool = SpreadsheetTool(store)
    result = await tool.execute(title="Empty")
    assert not result.success


@pytest.mark.asyncio
async def test_pdf_creates_valid_pdf(store: ResultStore):
    tool = PDFTool(store)
    result = await tool.execute(
        title="Safety Brief",
        outline="1. Scope\nKeep systems sandboxed.\n2. Actions\nReview permissions.",
    )
    assert result.success, result.error
    path = store.absolute_path(result.output["file_id"])
    raw = path.read_bytes()
    assert raw.startswith(b"%PDF")
    info = verify_pdf_bytes(raw)
    assert info["page_count"] >= 1
    assert "Safety" in info["text"] or "Scope" in info["text"]


@pytest.mark.asyncio
async def test_file_analysis_reads_docx(tmp_path: Path, store: ResultStore):
    doc_tool = DocumentTool(store)
    created = await doc_tool.execute(
        title="Analyzed Doc",
        sections=[{"title": "Body", "bullets": ["Unique mango volcano phrase"]}],
        filename="analyzed",
    )
    assert created.success
    # Copy into sandbox root (analysis reads workspace, not results/ by relative path from tools).
    # Analysis tool uses sandbox_root; ResultStore files live under results/.
    # Point analysis at the absolute file via relative path from sandbox.
    sandbox = tmp_path
    src = store.absolute_path(created.output["file_id"])
    assert src
    rel = f"results/{src.name}"
    analyzer = FileAnalysisTool(sandbox)
    result = await analyzer.execute(path=rel)
    assert result.success, result.error
    assert "mango volcano" in result.output["text_preview"].lower()


@pytest.mark.asyncio
async def test_office_timeout(store: ResultStore, monkeypatch):
    tool = PresentationTool(store)

    async def _slow(_tid: str):
        await asyncio.sleep(2)
        return b"x", "a", "pptx", {}

    monkeypatch.setattr(
        "app.tools.office.runner.DEFAULT_TIMEOUT_SECONDS",
        0.01,
    )
    from app.tools.office import runner as runner_mod

    async def _run_with_short_timeout(**kwargs):
        kwargs["timeout_seconds"] = 0.05
        kwargs["build"] = _slow
        return await runner_mod.run_office_job(**kwargs)

    result = await _run_with_short_timeout(
        tool_name="create_presentation",
        store=store,
        build=_slow,
        timeout_seconds=0.05,
    )
    assert not result.success
    assert result.metadata.get("status") == "timeout"


def test_planner_routes_presentation():
    planner = RuleBasedPlanner()
    action = planner.plan_next(
        AgentState(task=AgentTask(description="Сделай презентацию по запуску SaaS и перенеси её в PowerPoint"))
    )
    assert action.type == PlannedActionType.TOOL_CALL
    assert action.tool_name == "create_presentation"
    assert "outline" in action.tool_input


def test_planner_routes_pdf_and_xlsx():
    planner = RuleBasedPlanner()
    pdf = planner.plan_next(AgentState(task=AgentTask(description="Создай PDF отчёт по продажам")))
    assert pdf.tool_name == "create_pdf"
    xlsx = planner.plan_next(AgentState(task=AgentTask(description="Сделай excel таблицу бюджета")))
    assert xlsx.tool_name == "create_spreadsheet"


def test_planner_idempotent_after_presentation():
    planner = RuleBasedPlanner()
    steps = [
        AgentStep(
            index=0,
            step_type=AgentStepType.TOOL_CALL,
            tool_name="create_presentation",
            tool_input={"title": "X"},
            output={
                "download_url": "/api/v1/results/abc/download",
                "filename": "x.pptx",
                "summary": "Created",
            },
            success=True,
        )
    ]
    action = planner.plan_next(
        AgentState(task=AgentTask(description="Сделай презентацию про AI"), steps=steps)
    )
    assert action.type == PlannedActionType.FINAL_ANSWER
    assert "/api/v1/results/" in (action.final_answer or "")


def test_registry_registers_office_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path))
    get_default_tool_registry.cache_clear()
    # Force fresh settings path via build_default_registry with patched settings
    from app.config.settings import Settings
    from app.tools import registry as reg

    monkeypatch.setattr(
        reg,
        "get_settings",
        lambda: Settings(_env_file=None, AGENT_WORKSPACE_DIR=str(tmp_path), AI_PROVIDER="mock"),
    )
    get_default_tool_registry.cache_clear()
    registry = build_default_registry()
    names = {t.name for t in registry.list()}
    assert {
        "create_presentation",
        "create_document",
        "create_spreadsheet",
        "create_pdf",
        "analyze_file",
    } <= names
    get_default_tool_registry.cache_clear()


@pytest.mark.asyncio
async def test_download_endpoint_serves_file(tmp_path, monkeypatch):
    from app.api.routes import results as results_routes
    from app.main import app

    store = ResultStore(tmp_path)
    tool = PresentationTool(store)
    created = await tool.execute(
        title="API Deck", outline="1. Intro\nHello\n2. Outro\nBye"
    )
    assert created.success
    file_id = created.output["file_id"]

    monkeypatch.setattr(results_routes, "get_result_store", lambda: ResultStore(tmp_path))

    client = TestClient(app)
    meta = client.get(f"/api/v1/results/{file_id}")
    assert meta.status_code == 200, meta.text
    body = meta.json()
    assert body["download_url"].endswith("/download")
    assert "agent_workspace" not in body["download_url"]
    assert ":\\" not in body["download_url"]

    dl = client.get(f"/api/v1/results/{file_id}/download")
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"  # zip/pptx
    assert len(dl.content) > 1000

    denied = client.get("/api/v1/results/does-not-exist/download")
    assert denied.status_code >= 400


@pytest.mark.asyncio
async def test_agent_creates_presentation_end_to_end(tmp_path):
    from app.agent.agent import Agent
    from app.agent.executor import Executor
    from app.agent.tool_selector import ToolSelector
    from app.agent.verifier import Verifier
    from app.agent.models import AgentStatus, AgentTask
    from app.tools.registry import ToolRegistry

    store = ResultStore(tmp_path)
    registry = ToolRegistry()
    registry.register(PresentationTool(store))
    registry._result_store = store  # type: ignore[attr-defined]
    agent = Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        # No model gateway — planner final_answer must include download URL.
    )
    result = await agent.run(
        AgentTask(description="Сделай презентацию по запуску продукта в PowerPoint")
    )
    assert result.status == AgentStatus.COMPLETED
    assert result.success
    assert any(s.tool_name == "create_presentation" and s.success for s in result.steps)
    assert result.final_answer and "/api/v1/results/" in result.final_answer
    # File exists on disk
    step = next(s for s in result.steps if s.tool_name == "create_presentation")
    file_id = step.output["file_id"]
    assert store.absolute_path(file_id) is not None


def test_result_store_saves_many_files_concurrently_without_losing_manifest_entries(tmp_path: Path):
    import json
    from concurrent.futures import ThreadPoolExecutor

    store = ResultStore(tmp_path)

    def save(index: int):
        return store.save_bytes(
            f"payload-{index}".encode(),
            filename=f"result-{index}",
            media_type="text/plain",
            extension="txt",
            task_id=f"task-{index}",
            user_id=f"user-{index}",
        )

    with ThreadPoolExecutor(max_workers=32) as pool:
        records = list(pool.map(save, range(100)))

    assert len({record.file_id for record in records}) == 100
    manifest = json.loads((tmp_path / "results" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 100
    assert all(store.absolute_path(record.file_id).is_file() for record in records)


def test_result_store_returns_detached_metadata_records(tmp_path: Path):
    store = ResultStore(tmp_path)
    saved = store.save_bytes(
        b"private result",
        filename="private",
        media_type="text/plain",
        extension="txt",
        task_id="task-private",
        user_id="owner-a",
    )

    saved.user_id = "owner-b"
    loaded = store.get(saved.file_id, user_id="owner-a")

    assert loaded is not None
    assert loaded.user_id == "owner-a"
    assert store.get(saved.file_id, user_id="owner-b") is None
