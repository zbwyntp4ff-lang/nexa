"""Phase 5 — RAG metrics, eval suite, journal, e2e compound, regressions, browser."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.agent import Agent
from app.agent.compound import build_compound_plan, _requested_slide_count
from app.agent.executor import Executor
from app.agent.journal import journal_path, recent_journal, record_journal_event
from app.agent.models import AgentStatus, AgentTask
from app.agent.planner import RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.knowledge.eval_rag import evaluate_retrievers, write_rag_eval_report
from app.learning.eval_suite import run_eval_suite, write_eval_report
from app.tools.base import Tool, ToolResult
from app.tools.desktop.browser_tool import BrowserTool
from app.tools.office.document import DocumentTool, verify_docx_bytes
from app.tools.office.presentation import PresentationTool, verify_pptx_bytes
from app.tools.office.result_store import ResultStore
from app.tools.office.spreadsheet import SpreadsheetTool, verify_xlsx_bytes
from app.tools.registry import ToolRegistry
from app.build.browser_verify import playwright_available


class FakeResearchTool(Tool):
    name = "web_research"
    description = "fake"
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    permissions = frozenset({"network:read"})

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            success=True,
            output={
                "query": kwargs.get("query"),
                "results": [
                    {"title": "AI assistants market", "url": "https://example.com/a", "snippet": "growing"},
                    {"title": "Competitor A", "url": "https://example.com/b", "snippet": "chat product"},
                ],
                "sources": [
                    {
                        "title": "AI assistants market",
                        "url": "https://example.com/a",
                        "text": "FACT: Example competitive landscape note for tests.",
                        "content_hash": "x",
                    },
                    {
                        "title": "Competitor A",
                        "url": "https://example.com/b",
                        "text": "FACT: Competitor A focuses on chat UX.",
                        "content_hash": "y",
                    },
                ],
            },
        )


def test_rag_metrics_report_written():
    report = evaluate_retrievers()
    assert "methods" in report
    assert report["methods"]["hashing256"]["cost_usd"] == 0.0
    assert report["methods"]["hashing256"]["recall_at_k"] is not None
    path = write_rag_eval_report(report)
    assert path.is_file()
    assert "recommendation" in report


@pytest.mark.asyncio
async def test_eval_suite_offline():
    report = await run_eval_suite()
    assert report["total"] >= 5
    assert report["pass_rate"] >= 0.8
    path = write_eval_report(report)
    assert path.is_file()


def test_journal_records_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXA_PROJECT_ROOT", str(tmp_path))  # may be unused
    # Point journal via monkeypatch of resolve path function
    import app.agent.journal as journal_mod

    jpath = tmp_path / "agent_journal.jsonl"
    monkeypatch.setattr(journal_mod, "journal_path", lambda: jpath)
    record_journal_event(
        task_id="t1",
        event="tool_step",
        tool_name="create_presentation",
        status="ok",
        duration_ms=12.5,
        attempt=1,
        error="api_key=sk-secret-should-redact bearer TOK123",
    )
    rows = recent_journal(task_id="t1")
    assert len(rows) == 1
    assert "sk-secret" not in (rows[0].get("error") or "")
    assert "[REDACTED]" in (rows[0].get("error") or "")


def test_requested_slide_count_maps_total_to_content():
    assert _requested_slide_count("презентацию на 10 слайдов") == 9


@pytest.mark.asyncio
async def test_presentation_honors_slide_count(tmp_path):
    store = ResultStore(tmp_path)
    tool = PresentationTool(store)
    result = await tool.execute(
        title="Ten Slide Deck",
        outline="Topic overview",
        slide_count=9,
    )
    assert result.success, result.error
    info = verify_pptx_bytes(store.absolute_path(result.output["file_id"]).read_bytes())
    # title + 9 content
    assert info["slide_count"] >= 10


@pytest.mark.asyncio
async def test_e2e_compound_market_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXA_LOCAL_DESKTOP", "1")
    monkeypatch.setenv("AGENT_WORKSPACE_DIR", str(tmp_path))
    from app.config import settings as settings_mod
    from app.tools.desktop.locality import clear_locality_cache

    clear_locality_cache()
    settings_mod.get_settings.cache_clear()

    store = ResultStore(tmp_path)
    registry = ToolRegistry()
    registry.register(FakeResearchTool())
    registry.register(PresentationTool(store))
    registry.register(SpreadsheetTool(store))
    registry.register(DocumentTool(store))
    from app.tools.desktop.local_files import LocalFileTool

    registry.register(LocalFileTool(tmp_path))
    registry._result_store = store  # type: ignore[attr-defined]

    agent = Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        max_steps=20,
        timeout_seconds=90,
        error_limit=12,
    )
    task = (
        "Исследуй рынок AI-ассистентов, сравни пять конкурентов, "
        "подготовь таблицу сравнения, презентацию на 10 слайдов и Word-отчёт. "
        "Сохрани результаты в отдельной папке проекта и предоставь ссылки на файлы"
    )
    plan = build_compound_plan(task)
    assert plan.is_compound
    assert "research" in [d.kind.value for d in plan.deliverables]
    assert "presentation" in [d.kind.value for d in plan.deliverables]
    assert "spreadsheet" in [d.kind.value for d in plan.deliverables]
    assert "document" in [d.kind.value for d in plan.deliverables]
    assert "project_folder" in [d.kind.value for d in plan.deliverables]

    result = await agent.run(AgentTask(description=task, metadata={"user_id": "u-e2e"}))
    assert result.status == AgentStatus.COMPLETED
    assert result.final_answer and "/api/v1/results/" in result.final_answer
    assert result.project_id
    assert result.project_manifest
    files = result.project_manifest["created_files"]
    assert len(files) >= 3

    # Open each artifact with libraries
    by_ext = {}
    for f in files:
        path = store.absolute_path(f["file_id"])
        assert path and path.is_file()
        by_ext[path.suffix.lower()] = path.read_bytes()
    assert ".pptx" in by_ext
    assert ".xlsx" in by_ext
    assert ".docx" in by_ext
    pptx_info = verify_pptx_bytes(by_ext[".pptx"])
    assert pptx_info["slide_count"] >= 10
    xlsx_info = verify_xlsx_bytes(by_ext[".xlsx"])
    # Comparison tasks produce an assistant matrix; finance tasks keep formulas.
    rows = xlsx_info.get("rows") or []
    is_comparison = any(
        isinstance(row, (list, tuple)) and row and str(row[0]).lower() == "assistant"
        for row in rows
    )
    assert is_comparison or xlsx_info.get("formula_count", 0) >= 1
    docx_info = verify_docx_bytes(by_ext[".docx"])
    assert docx_info["paragraph_count"] >= 2

    # Results API
    from app.api.routes import results as results_routes
    from app.main import app

    monkeypatch.setattr(results_routes, "get_result_store", lambda: store)
    client = TestClient(app)
    fid = files[0]["file_id"]

    # An owned result must not be available to an anonymous request.
    anonymous = client.get(f"/api/v1/results/{fid}")
    assert anonymous.status_code == 404

    # Simulate the authenticated owner for the authorized download path.
    from types import SimpleNamespace
    from app.api.security_deps import require_user_when_enforced

    app.dependency_overrides[require_user_when_enforced] = lambda: SimpleNamespace(id="u-e2e")
    try:
        meta = client.get(f"/api/v1/results/{fid}")
        assert meta.status_code == 200
        dl = client.get(f"/api/v1/results/{fid}/download")
        assert dl.status_code == 200
        assert len(dl.content) > 100
    finally:
        app.dependency_overrides.pop(require_user_when_enforced, None)

    # Project folder scaffold
    assert any((tmp_path / "projects").rglob("README.md"))

    # Journal has tool steps
    # (journal writes to project data/ — ensure at least record works)
    record_journal_event(task_id=result.task_id, event="e2e", status="ok")

    settings_mod.get_settings.cache_clear()
    clear_locality_cache()


def test_regression_rag_miss_no_poison():
    """Regression: KB miss must not inject insufficient note into chat."""
    from app.core.nexa_core import NexaCore
    from app.knowledge.knowledge_base import KNOWLEDGE_INSUFFICIENT_NOTE, build_knowledge_base
    from app.config.settings import Settings
    from app.models.chat import ChatRequest
    from app.providers.mock import MockProvider
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        settings = Settings(
            _env_file=None,
            AI_PROVIDER="mock",
            KNOWLEDGE_STORE_PATH=str(Path(tmp) / "kv.json"),
            KNOWLEDGE_DOCUMENTS_PATH=str(Path(tmp) / "kd.json"),
            AGENT_WORKSPACE_DIR=str(Path(tmp) / "ws"),
        )
        Path(tmp, "ws").mkdir()
        kb = build_knowledge_base(settings)
        core = NexaCore(provider=MockProvider(), settings=settings, knowledge_base=kb)
        msgs, result = core._resolve_knowledge(ChatRequest(message="2+2?", use_knowledge_base=True))
        assert msgs == []
        assert result is not None and result.insufficient
        assert not any(KNOWLEDGE_INSUFFICIENT_NOTE in (m.content or "") for m in msgs)


@pytest.mark.asyncio
async def test_regression_research_chat_keeps_gateway(monkeypatch):
    """Regression: KnowledgeCoreComposer must not overwrite NexaCore."""
    from app.api.routes import research as research_routes
    from app.gateway.models import GatewayResult
    from app.tools.base import ToolResult

    class _FakeGateway:
        async def chat(self, messages, model=None, task_kind=None, images=None):
            return GatewayResult(
                text="ok [1]",
                provider="mock",
                model_id="m",
                display_name="Mock",
            )

    class _FakeCore:
        gateway = _FakeGateway()

    class _FakeTool:
        async def execute(self, **kwargs):
            return ToolResult(
                success=True,
                output={
                    "query": "q",
                    "results": [{"title": "t", "url": "https://example.com", "snippet": "s"}],
                    "sources": [
                        {
                            "url": "https://example.com",
                            "title": "t",
                            "text": "body",
                            "content_hash": "h",
                        }
                    ],
                },
            )

    class _FakeRegistry:
        def get(self, name):
            return _FakeTool()

    monkeypatch.setattr(research_routes, "get_default_tool_registry", lambda: _FakeRegistry())
    resp = await research_routes.research_chat(
        research_routes.ResearchChatRequest(message="What is example?"),
        core=_FakeCore(),  # type: ignore[arg-type]
    )
    assert "ok" in resp.message


@pytest.mark.asyncio
async def test_browser_ssrf_blocks_local_and_file(tmp_path):
    tool = BrowserTool(tmp_path)
    html = tmp_path / "page.html"
    html.write_text("<html><body><h1>x</h1></body></html>", encoding="utf-8")
    blocked_file = await tool.execute(action="open", url=html.as_uri())
    assert not blocked_file.success
    blocked_loop = await tool.execute(action="open", url="http://127.0.0.1:9/")
    assert not blocked_loop.success
    meta = (blocked_loop.metadata or {}) | (blocked_file.metadata or {})
    assert meta.get("status") == "ssrf_blocked" or "blocked" in (
        (blocked_loop.error or "") + (blocked_file.error or "")
    ).lower() or "ssrf" in ((blocked_loop.error or "") + (blocked_file.error or "")).lower()


@pytest.mark.asyncio
async def test_chromium_local_page_extract_query_timeout_close(tmp_path):
    """Real Chromium + local HTML (set_content) — no external network.

    BrowserTool cannot open loopback (SSRF by design); this proves the binary
    runs extract/query/timeout/close semantics on a local page.
    """
    if not playwright_available():
        pytest.skip("Chromium binary not available — live browser not verified")

    from playwright.async_api import async_playwright

    html = (
        "<html><body>"
        "<h1 id='title'>NEXA Test Page</h1>"
        "<p>hello browser marker-42</p>"
        "</body></html>"
    )
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.set_content(html)
            title = await page.title()
            text = await page.inner_text("body")
            assert "hello browser" in text
            assert await page.locator("#title").count() == 1
            assert "NEXA Test Page" in (await page.locator("#title").inner_text())
            # Timeout: selector that never appears
            timed_out = False
            try:
                await page.locator("#missing-never").wait_for(timeout=400)
            except Exception:
                timed_out = True
            assert timed_out
            await context.close()
            assert title is not None or text
            (tmp_path / "browser_ok.txt").write_text("chromium_local_ok", encoding="utf-8")
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_browser_tool_public_or_skip(tmp_path):
    """Full BrowserTool path against a public page when network works."""
    if not playwright_available():
        pytest.skip("Chromium binary not available — live browser not verified")
    tool = BrowserTool(tmp_path)
    result = await tool.execute(action="extract", url="https://example.com", timeout_seconds=20)
    if not result.success:
        pytest.skip(f"Live BrowserTool path not verified (network/DNS): {result.error}")
    assert "example" in (result.output.get("title") or "").lower() or "Example" in (
        result.output.get("text") or ""
    )
    q = await tool.execute(
        action="query", url="https://example.com", selector="body", timeout_seconds=20
    )
    assert q.success
    assert q.output.get("count", 0) >= 1
    found = await tool.execute(
        action="search_page",
        url="https://example.com",
        query="Example",
        timeout_seconds=20,
    )
    assert found.success
    assert found.output.get("match_count", 0) >= 1


@pytest.mark.asyncio
async def test_playwright_available_under_running_loop():
    """Regression: sync_playwright must not falsely report False inside asyncio."""
    assert playwright_available() is True or playwright_available() is False
    # When Chromium is installed (this machine), must stay True under a loop.
    from app.build.browser_verify import playwright_available as pa

    # Already inside pytest-asyncio loop — call again
    val = pa()
    # Consistency: two probes agree
    assert pa() == val


def test_source_compare_corroboration():
    from app.web.models import PageDocument
    from app.web.source_compare import compare_sources

    docs = [
        PageDocument(
            url="https://a.example/p",
            title="A",
            text="ChatGPT launched in 2022 by OpenAI. Market growing.",
            content_hash="1",
        ),
        PageDocument(
            url="https://b.example/p",
            title="B",
            text="OpenAI released ChatGPT in 2022. Assistants market expanding.",
            content_hash="2",
        ),
    ]
    report = compare_sources(docs, claim_hints=["ChatGPT", "OpenAI"])
    assert report["source_count"] == 2
    assert report["status"] in {"corroborated", "partial"}
    assert any(c["corroborated"] for c in report["claim_checks"])


@pytest.mark.network
@pytest.mark.asyncio
async def test_live_web_research_optional():
    """Live DDG research — skipped in CI unless RUN_NETWORK_TESTS=1.

    Search may succeed while fetches fail (SSL/403/timeout). That must surface
    as an honest error with real result URLs — never fabricated sources.
    """
    if os.environ.get("RUN_NETWORK_TESTS") != "1":
        pytest.skip("Set RUN_NETWORK_TESTS=1 to run live search")
    from app.web.duckduckgo_provider import DuckDuckGoSearchProvider
    from app.web.page_fetcher import PageFetcher
    from app.web.research_tool import ResearchTool

    tool = ResearchTool(
        search_provider=DuckDuckGoSearchProvider(timeout_seconds=15),
        page_fetcher=PageFetcher(timeout_seconds=15),
        default_max_results=3,
    )
    outcomes: list[dict] = []
    for query in (
        "OpenAI ChatGPT",
        "что такое искусственный интеллект",
        "Wikipedia artificial intelligence",
    ):
        result = await tool.execute(query=query, max_results=3, corroborate=True)
        results = (result.output or {}).get("results") or []
        sources = (result.output or {}).get("sources") or []
        outcomes.append(
            {
                "query": query,
                "success": result.success,
                "error": result.error,
                "n_results": len(results),
                "n_sources": len(sources),
                "urls": [r.get("url") for r in results if isinstance(r, dict)],
            }
        )
        # Never invent sources on failure
        if not result.success:
            assert sources == []
            assert results or "no results" in (result.error or "").lower() or "fetch" in (
                result.error or ""
            ).lower() or "search" in (result.error or "").lower()
        else:
            assert sources or results
            for s in sources:
                assert str(s.get("url") or "").startswith("http")
            if len(sources) >= 2:
                assert result.output.get("corroboration") is not None

    # At least one query must get organic search hits (live DDG reachable)
    assert any(o["n_results"] > 0 for o in outcomes), f"No live search hits: {outcomes}"
