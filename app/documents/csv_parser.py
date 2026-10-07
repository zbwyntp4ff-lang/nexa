"""Parses CSV files into structured, tab-aligned text."""
from __future__ import annotations
import csv
import io
from app.documents.base import DocumentParser
from app.documents.models import ParsedDocument
from app.models.errors import DocumentParsingError
class CsvParser(DocumentParser):
    formats = frozenset({"csv"})
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        try:
            decoded = raw.decode("utf-8-sig")
            rows = list(csv.reader(io.StringIO(decoded)))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise DocumentParsingError(f"Invalid CSV in '{filename}': {exc}") from exc
        header = rows[0] if rows else []
        body = rows[1:] if rows else []
        text = "\n".join(" | ".join(row) for row in rows)
        return ParsedDocument(
            filename=filename,
            format="csv",
            text=text,
            metadata={
                "row_count": len(body),
                "column_count": len(header),
                "header": header,
            },
        )
