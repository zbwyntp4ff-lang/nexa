"""Parses DOCX files by extracting their text content (via ``python-docx``)."""
from __future__ import annotations
import io
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
from app.models.errors import DocumentParsingError
class DocxParser(DocumentParser):
    formats = frozenset({"docx"})
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        try:
            import docx
        except ImportError as exc:  # pragma: no cover - dependency always pinned
            raise DocumentParsingError("The 'python-docx' package is required to parse DOCX files.") from exc
        try:
            document = docx.Document(io.BytesIO(raw))
            paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
            table_rows = [
                " | ".join(cell.text for cell in row.cells)
                for table in document.tables
                for row in table.rows
            ]
        except Exception as exc:  # noqa: BLE001 - normalize any python-docx failure
            raise DocumentParsingError(f"Could not parse DOCX '{filename}': {exc}") from exc
        text = "\n".join(paragraphs + table_rows)
        return ParsedDocument(
            filename=filename,
            format="docx",
            text=text,
            metadata={"paragraph_count": len(paragraphs), "table_count": len(document.tables)},
        )
