"""Verification layer for office / research tool outputs."""
from __future__ import annotations

from typing import Any

from app.agent.models import AgentStep
from app.core.logging_config import get_logger
from app.tools.office.document import verify_docx_bytes
from app.tools.office.pdf import verify_pdf_bytes
from app.tools.office.presentation import verify_pptx_bytes
from app.tools.office.result_store import ResultStore
from app.tools.office.spreadsheet import verify_xlsx_bytes
from app.tools.registry import ToolRegistry

logger = get_logger("nexa.agent.verify")


def verify_office_output(
    tool_name: str,
    output: Any,
    *,
    store: ResultStore | None,
    tool_input: dict | None = None,
) -> tuple[bool, str]:
    """Return (ok, detail). Does not trust tool success alone."""
    if not isinstance(output, dict):
        return False, "Office tool output must be a dict with file_id/download_url."
    file_id = output.get("file_id")
    download_url = output.get("download_url") or ""
    if not file_id or not str(download_url).startswith("/api/v1/results/"):
        return False, "Missing file_id or invalid download_url (server paths are not allowed)."
    if store is None:
        return False, "Result store unavailable for verification."
    path = store.absolute_path(str(file_id))
    if path is None or not path.is_file():
        return False, "Generated file missing on disk."
    data = path.read_bytes()
    if len(data) < 100:
        return False, "Generated file too small."

    try:
        if tool_name == "create_presentation":
            info = verify_pptx_bytes(data)
            if info["slide_count"] < 2:
                return False, f"Presentation has too few slides ({info['slide_count']})."
            empty = sum(1 for t in info["titles"] if not (t or "").strip())
            if empty > info["slide_count"] // 2:
                return False, "Too many empty slides."
            return True, f"pptx ok slides={info['slide_count']}"

        if tool_name == "create_document":
            info = verify_docx_bytes(data)
            if info["paragraph_count"] < 1:
                return False, "DOCX has no paragraphs."
            return True, f"docx ok paras={info['paragraph_count']}"

        if tool_name == "create_spreadsheet":
            info = verify_xlsx_bytes(data)
            if info["row_count"] < 2:
                return False, "Spreadsheet has insufficient rows."
            # Prefer formulas when financial_model was requested.
            wants_formulas = bool((tool_input or {}).get("financial_model"))
            if wants_formulas:
                formula_cells = _count_formulas(data)
                if formula_cells < 1:
                    return False, "Financial model expected formulas (=SUM/etc)."
                return True, f"xlsx ok rows={info['row_count']} formulas={formula_cells}"
            return True, f"xlsx ok rows={info['row_count']}"

        if tool_name == "create_pdf":
            if not data.startswith(b"%PDF"):
                return False, "PDF missing %PDF header."
            info = verify_pdf_bytes(data)
            if info["page_count"] < 1:
                return False, "PDF has no pages."
            return True, f"pdf ok pages={info['page_count']}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("artifact verify failed tool=%s err=%s", tool_name, exc.__class__.__name__)
        return False, f"Open/parse failed: {exc.__class__.__name__}"

    return True, "ok"


def verify_research_output(output: Any) -> tuple[bool, str]:
    if not isinstance(output, dict):
        return False, "Research output must be a dict."
    sources = output.get("sources") or []
    results = output.get("results") or []
    if sources:
        bad = [s for s in sources if isinstance(s, dict) and not str(s.get("url") or "").startswith("http")]
        if len(bad) == len(sources):
            return False, "Sources lack http(s) URLs."
        return True, f"research ok sources={len(sources)}"
    if results:
        return True, f"research ok results={len(results)} (snippets only)"
    return False, "Research returned no sources or results."


def _count_formulas(data: bytes) -> int:
    from io import BytesIO

    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data))
    ws = wb.active
    count = 0
    for row in ws.iter_rows():
        for cell in row:
            val = cell.value
            if isinstance(val, str) and val.startswith("="):
                count += 1
    return count


class ArtifactVerifier:
    """Verifier mixin used by the agent Verifier for Phase 3 tools."""

    OFFICE_TOOLS = frozenset(
        {
            "create_presentation",
            "create_document",
            "create_spreadsheet",
            "create_pdf",
        }
    )

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def _store(self) -> ResultStore | None:
        store = getattr(self._registry, "_result_store", None)
        if isinstance(store, ResultStore):
            return store
        # Tools constructed outside build_default_registry still hold a ResultStore.
        for name in self.OFFICE_TOOLS:
            try:
                tool = self._registry.get(name)
            except Exception:  # noqa: BLE001
                continue
            candidate = getattr(tool, "_store", None)
            if isinstance(candidate, ResultStore):
                return candidate
        return None

    async def verify(self, step: AgentStep) -> tuple[bool, str]:
        if step.tool_name in self.OFFICE_TOOLS:
            ok, detail = verify_office_output(
                step.tool_name or "",
                step.output,
                store=self._store(),
                tool_input=step.tool_input,
            )
            return ok, detail
        if step.tool_name == "web_research":
            return verify_research_output(step.output)
        return True, "no special verification"
