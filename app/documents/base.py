"""The ``DocumentParser`` interface for turning a document into structured text."""
from __future__ import annotations
from abc import ABC, abstractmethod
from app.documents.models import ParsedDocument
class DocumentParser(ABC):
    """Parses one document format into a :class:`ParsedDocument`.
    Implementations must only *read* document content - never execute,
    evaluate, or shell out to anything derived from the file.
    """
    formats: frozenset[str]
    @abstractmethod
    def parse(self, raw: bytes, filename: str) -> ParsedDocument:
        """Parse raw bytes into structured text content.
        Raises:
            app.models.errors.DocumentParsingError: If the document is
                corrupt or otherwise cannot be parsed.
        """
