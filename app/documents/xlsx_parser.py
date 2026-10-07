"""Parses XLSX spreadsheets by extracting cell text (via ``openpyxl``)."""
from __future__ import annotations
import io
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
from app.models.errors import DocumentParsingError
MAX_ROWS_PER_SHEET = 5_000
class XlsxParser(DocumentParser):
    formats = frozenset({"xlsx"})
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover - dependency always pinned
            raise DocumentParsingError("The 'openpyxl' package is required to parse XLSX files.") from exc
        try:
            # read_only avoids loading the whole workbook into memory; data_only
            # skips formula source text in favor of last-computed values.
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 - normalize any openpyxl failure
            raise DocumentParsingError(f"Could not parse XLSX '{filename}': {exc}") from exc
        sheet_texts: list[str] = []
        sheet_names: list[str] = []
        row_count = 0
        try:
            for sheet in workbook.worksheets:
                sheet_names.append(sheet.title)
                rows_text: list[str] = []
                for index, row in enumerate(sheet.iter_rows(values_only=True)):
                    if index >= MAX_ROWS_PER_SHEET:
                        rows_text.append("... (truncated)")
                        break
                    rows_text.append(" | ".join("" if cell is None else str(cell) for cell in row))
                    row_count += 1
                sheet_texts.append(f"# {sheet.title}\n" + "\n".join(rows_text))
        finally:
            workbook.close()
        text = "\n\n".join(sheet_texts)
        return ParsedDocument(
            filename=filename,
            format="xlsx",
            text=text,
            metadata={"sheet_count": len(sheet_names), "sheet_names": sheet_names, "row_count": row_count},
        )
