"""Phase 6 live compound E2E — real web research + real office artifacts.

Does not invent successful search. Writes a machine-readable report under
data/eval_reports/beta_live_e2e.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.agent.agent import Agent
from app.agent.compound import build_compound_plan
from app.agent.executor import Executor
from app.agent.models import AgentStatus, AgentTask
from app.agent.planner import RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.core.paths import resolve_under_project_root
from app.tools.desktop.local_files import LocalFileTool
from app.tools.office.document import DocumentTool, verify_docx_bytes
from app.tools.office.presentation import PresentationTool, verify_pptx_bytes
from app.tools.office.result_store import ResultStore
from app.tools.office.spreadsheet import SpreadsheetTool, verify_xlsx_bytes
from app.tools.registry import ToolRegistry
from app.web.duckduckgo_provider import DuckDuckGoSearchProvider
from app.web.page_fetcher import PageFetcher
from app.web.research_tool import ResearchTool


TASK = (
    "Исследуй пять AI-ассистентов, сравни их возможности, ограничения и модели монетизации. "
    "Подготовь сравнительную таблицу в Excel, презентацию на 10 слайдов и подробный Word-отчёт. "
    "Сохрани результаты в папку одного проекта и предоставь ссылки на скачивание"
)


async def main() -> None:
    os.environ.setdefault("NEXA_LOCAL_DESKTOP", "1")
    report: dict = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": TASK,
        "parts": {},
        "status": "running",
    }

    # Live research probe first (honest)
    research = ResearchTool(
        search_provider=DuckDuckGoSearchProvider(timeout_seconds=20),
        page_fetcher=PageFetcher(timeout_seconds=20),
        default_max_results=5,
    )
    live = await research.execute(
        query="AI assistants ChatGPT Claude Gemini Copilot monetization comparison",
        max_results=5,
        corroborate=True,
        claim_hints=["ChatGPT", "Claude", "Gemini", "Copilot"],
    )
    report["parts"]["live_research"] = {
        "success": live.success,
        "error": live.error,
        "n_results": len((live.output or {}).get("results") or []),
        "n_sources": len((live.output or {}).get("sources") or []),
        "result_urls": [
            r.get("url") for r in ((live.output or {}).get("results") or []) if isinstance(r, dict)
        ],
        "source_urls": [
            s.get("url") for s in ((live.output or {}).get("sources") or []) if isinstance(s, dict)
        ],
        "corroboration": (live.output or {}).get("corroboration"),
        "mocked": False,
    }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        os.environ["AGENT_WORKSPACE_DIR"] = str(root)
        store = ResultStore(root)
        registry = ToolRegistry()
        registry.register(research)
        registry.register(PresentationTool(store))
        registry.register(SpreadsheetTool(store))
        registry.register(DocumentTool(store))
        registry.register(LocalFileTool(root))
        registry._result_store = store  # type: ignore[attr-defined]

        plan = build_compound_plan(TASK)
        report["parts"]["compound_plan"] = {
            "deliverables": [d.kind.value for d in plan.deliverables],
            "is_compound": plan.is_compound,
        }

        agent = Agent(
            planner=RuleBasedPlanner(),
            tool_selector=ToolSelector(registry),
            executor=Executor(registry),
            verifier=Verifier(registry),
            max_steps=24,
            timeout_seconds=180,
            error_limit=14,
        )
        result = await agent.run(AgentTask(description=TASK, metadata={"user_id": "beta-e2e"}))
        report["parts"]["agent"] = {
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "completed": result.status == AgentStatus.COMPLETED,
            "final_answer_has_download": bool(
                result.final_answer and "/api/v1/results/" in (result.final_answer or "")
            ),
            "project_id": result.project_id,
            "n_manifest_files": len((result.project_manifest or {}).get("created_files") or []),
            "error": result.error if hasattr(result, "error") else None,
            "live_search_used": True,
            "research_mocked": False,
        }

        files_ok = {}
        for f in (result.project_manifest or {}).get("created_files") or []:
            fid = f.get("file_id")
            path = store.absolute_path(fid) if fid else None
            if not path or not path.is_file():
                files_ok[str(fid)] = {"exists": False}
                continue
            data = path.read_bytes()
            ext = path.suffix.lower()
            info: dict = {"exists": True, "bytes": len(data), "ext": ext}
            try:
                if ext == ".pptx":
                    info["verify"] = verify_pptx_bytes(data)
                elif ext == ".xlsx":
                    info["verify"] = verify_xlsx_bytes(data)
                elif ext == ".docx":
                    info["verify"] = verify_docx_bytes(data)
            except Exception as exc:  # noqa: BLE001
                info["verify_error"] = f"{type(exc).__name__}: {exc}"
            files_ok[path.name] = info
        report["parts"]["artifacts"] = files_ok
        report["parts"]["assumption_check"] = {
            "final_mentions_assumption": "ASSUMPTION" in (result.final_answer or ""),
            "note": "Figures without live sources must be labeled ASSUMPTION",
        }

    if not live.success and report["parts"]["agent"].get("completed"):
        report["status"] = "partial"
        report["warning"] = (
            "Agent completed office deliverables but live research failed or returned no sources. "
            "Do not treat sources as verified."
        )
    elif report["parts"]["agent"].get("completed") and live.success:
        report["status"] = "completed"
    else:
        report["status"] = "failed"

    out = resolve_under_project_root("data/eval_reports/beta_live_e2e.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "path": str(out), "live_sources": report["parts"]["live_research"]["n_sources"]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
