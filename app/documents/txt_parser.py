"""Parses plain text files."""
from __future__ import annotations
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
class TxtParser(DocumentParser):
    formats = frozenset({"txt", "text", "md", "markdown"})
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        text = raw.decode("utf-8", errors="replace")
        return ParsedDocument(
            filename=filename,
            format="txt",
            text=text,
            metadata={"char_count": len(text)},
        )
