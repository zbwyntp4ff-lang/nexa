"""SpreadsheetTool — create real XLSX files (optional financial model with formulas)."""
from __future__ import annotations

import io
from typing import Any

from app.tools.base import Tool, ToolResult
from app.tools.office.outline import coerce_table_rows
from app.tools.office.result_store import ResultStore
from app.tools.office.runner import run_office_job


class SpreadsheetTool(Tool):
    name = "create_spreadsheet"
    description = (
        "Create an Excel (.xlsx) workbook with a data table or labeled financial model "
        "(formulas + ASSUMPTION placeholders). Returns a download_url."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Sheet / workbook title."},
            "rows": {
                "type": "array",
                "description": "Rows as lists or list of objects. First row may be headers.",
            },
            "csv_text": {"type": "string", "description": "Optional CSV/TSV text as data source."},
            "financial_model": {
                "type": "boolean",
                "description": "Build an illustrative financial model with Excel formulas.",
            },
            "assumptions_note": {"type": "string"},
            "source_text": {"type": "string"},
            "filename": {"type": "string"},
            "task_id": {"type": "string"},
            "user_id": {"type": "string"},
        },
        "required": [],
    }
    permissions = frozenset({"filesystem:write"})

    def __init__(self, store: ResultStore) -> None:
        self._store = store

    async def execute(self, **kwargs: Any) -> ToolResult:
        title = str(kwargs.get("title") or "Sheet1").strip() or "Sheet1"
        rows_in = kwargs.get("rows")
        csv_text = kwargs.get("csv_text")
        financial_model = bool(kwargs.get("financial_model"))
        assumptions_note = str(kwargs.get("assumptions_note") or "")
        filename = str(kwargs.get("filename") or title or "spreadsheet")

        if not financial_model and rows_in is None and not csv_text:
            return ToolResult(
                success=False,
                error="Provide rows, csv_text, or financial_model=true to create a spreadsheet.",
                metadata={"status": "invalid_input"},
            )

        rows = (
            None
            if financial_model and rows_in is None and not csv_text
            else coerce_table_rows(rows_in if rows_in is not None else csv_text)
        )

        async def _build(_tid: str) -> tuple[bytes, str, str, dict[str, Any]]:
            if financial_model:
                data = _build_financial_xlsx(
                    title=title,
                    assumptions_note=assumptions_note,
                )
                meta = {
                    "rows": 8,
                    "formulas": True,
                    "summary": (
                        f"Created financial model XLSX «{title}» with formulas. "
                        "Figures are ASSUMPTIONS, not researched facts."
                    ),
                }
            else:
                assert rows is not None
                data = _build_xlsx(title=title, rows=rows)
                meta = {
                    "rows": len(rows),
                    "summary": f"Created XLSX «{title}» with {len(rows)} rows.",
                }
            return data, filename, "xlsx", meta

        return await run_office_job(
            tool_name=self.name,
            store=self._store,
            build=_build,
            task_id=kwargs.get("task_id") if isinstance(kwargs.get("task_id"), str) else None,
            user_id=kwargs.get("user_id") if isinstance(kwargs.get("user_id"), str) else None,
        )


def _build_xlsx(*, title: str, rows: list[list[str]]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    safe_title = "".join(c for c in title if c not in r"[]:*?/\\")[:31] or "Sheet1"
    ws.title = safe_title

    header_fill = PatternFill("solid", fgColor="1E1B4B")
    header_font = Font(color="E8E4FF", bold=True)

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=_cell_value(value))
            if r_idx == 1:
                cell.fill = header_fill
                cell.font = header_font

    _autosize(ws)
    return _save(wb)


def _build_financial_xlsx(*, title: str, assumptions_note: str) -> bytes:
    """Illustrative 12-month model with SUM/product formulas — values are ASSUMPTIONS."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    safe_title = "".join(c for c in title if c not in r"[]:*?/\\")[:31] or "Model"
    ws.title = safe_title

    note = assumptions_note or (
        "ASSUMPTION: Placeholder figures for planning only — not market facts."
    )
    ws["A1"] = "NEXA Financial Model (ASSUMPTIONS)"
    ws["A1"].font = Font(bold=True, color="1E1B4B", size=14)
    ws["A2"] = note
    ws.merge_cells("A2:F2")

    headers = ["Metric", "M1", "M2", "M3", "Total", "Notes"]
    header_fill = PatternFill("solid", fgColor="1E1B4B")
    header_font = Font(color="E8E4FF", bold=True)
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.fill = header_fill
        cell.font = header_font

    # ASSUMPTION inputs
    ws["A5"] = "Customers (ASSUMPTION)"
    ws["B5"] = 10
    ws["C5"] = 15
    ws["D5"] = 22
    ws["E5"] = "=SUM(B5:D5)"
    ws["F5"] = "ASSUMPTION — replace with research"

    ws["A6"] = "ARPU USD (ASSUMPTION)"
    ws["B6"] = 49
    ws["C6"] = 49
    ws["D6"] = 59
    ws["E6"] = "=AVERAGE(B6:D6)"
    ws["F6"] = "ASSUMPTION"

    ws["A7"] = "Revenue"
    ws["B7"] = "=B5*B6"
    ws["C7"] = "=C5*C6"
    ws["D7"] = "=D5*D6"
    ws["E7"] = "=SUM(B7:D7)"
    ws["F7"] = "Formula: customers × ARPU"

    ws["A8"] = "COGS (ASSUMPTION %)"
    ws["B8"] = 0.25
    ws["C8"] = 0.25
    ws["D8"] = 0.22
    ws["E8"] = "=AVERAGE(B8:D8)"
    ws["F8"] = "ASSUMPTION fraction of revenue"

    ws["A9"] = "Gross profit"
    ws["B9"] = "=B7*(1-B8)"
    ws["C9"] = "=C7*(1-C8)"
    ws["D9"] = "=D7*(1-D8)"
    ws["E9"] = "=SUM(B9:D9)"
    ws["F9"] = "Formula"

    ws["A10"] = "OpEx (ASSUMPTION)"
    ws["B10"] = 800
    ws["C10"] = 900
    ws["D10"] = 1000
    ws["E10"] = "=SUM(B10:D10)"
    ws["F10"] = "ASSUMPTION"

    ws["A11"] = "Net (illustrative)"
    ws["B11"] = "=B9-B10"
    ws["C11"] = "=C9-C10"
    ws["D11"] = "=D9-D10"
    ws["E11"] = "=SUM(B11:D11)"
    ws["F11"] = "Not a forecast of real returns"

    _autosize(ws)
    return _save(wb)


def _cell_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("="):
        return value
    return value


def _autosize(ws) -> None:
    for col in ws.columns:
        max_len = 0
        letter = col[0].column_letter
        for cell in col:
            max_len = max(max_len, len(str(cell.value or "")))
        ws.column_dimensions[letter].width = min(max(10, max_len + 2), 48)


def _save(wb) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()
    if len(data) < 500:
        raise ValueError("Generated XLSX appears too small to be valid.")
    return data


def verify_xlsx_bytes(data: bytes) -> dict[str, Any]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    values = [[cell.value for cell in row] for row in ws.iter_rows()]
    formulas = sum(
        1
        for row in values
        for cell in row
        if isinstance(cell, str) and cell.startswith("=")
    )
    return {
        "sheet": ws.title,
        "row_count": len(values),
        "rows": values[:20],
        "formula_count": formulas,
    }
