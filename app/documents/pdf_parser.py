"""Parses PDF files by extracting their text content (via ``pypdf``)."""
from __future__ import annotations
import io
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
from app.models.errors import DocumentParsingError
class PdfParser(DocumentParser):
    formats = frozenset({"pdf"})
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency always pinned
            raise DocumentParsingError("The 'pypdf' package is required to parse PDF files.") from exc
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages_text = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # noqa: BLE001 - normalize any pypdf failure
            raise DocumentParsingError(f"Could not parse PDF '{filename}': {exc}") from exc
        text = "\n\n".join(pages_text).strip()
        return ParsedDocument(
            filename=filename,
            format="pdf",
            text=text,
            metadata={"page_count": len(reader.pages)},
        )
