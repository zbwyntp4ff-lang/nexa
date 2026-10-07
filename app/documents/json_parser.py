"""Parses JSON files into readable, structured text."""
from __future__ import annotations
import json
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
from app.models.errors import DocumentParsingError
class JsonParser(DocumentParser):
    formats = frozenset({"json"})
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DocumentParsingError(f"Invalid JSON in '{filename}': {exc}") from exc
        text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False)
        if isinstance(data, list):
            item_count = len(data)
        elif isinstance(data, dict):
            item_count = len(data)
        else:
            item_count = 1
        return ParsedDocument(
            filename=filename,
            format="json",
            text=text,
            metadata={"type": type(data).__name__, "item_count": item_count},
        )
