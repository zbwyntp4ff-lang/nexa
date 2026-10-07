"""``CitationManager`` (Part 9).
Builds citations strictly from chunks that were *actually* included in a
model's context - never invents a source, and never cites a document that
wasn't retrieved.
"""
from __future__ import annotations
from app.knowledge.document_store import DocumentStore
from app.knowledge.models import Citation, RetrievedChunk
class CitationManager:
    def __init__(self, document_store: DocumentStore) -> None:
        self._documents = document_store
    def build(self, retrieved: list[RetrievedChunk]) -> list[Citation]:
        citations: list[Citation] = []
        for index, chunk in enumerate(retrieved, start=1):
            doc = self._documents.get(chunk.document_id)
            citations.append(
                Citation(
                    index=index,
                    document_id=chunk.document_id,
                    filename=doc.filename if doc else chunk.document_id,
                    source=doc.source if doc else chunk.document_id,
                    page=chunk.page,
                    section=chunk.section,
                )
            )
        return citations
    @staticmethod
    def format(citations: list[Citation]) -> str:
        """Render citations as the "Sources:" block appended to an answer."""
        if not citations:
            return ""
        lines = ["Sources:"]
        for citation in citations:
            suffix = f", page {citation.page}" if citation.page else f", {citation.section}" if citation.section else ""
            lines.append(f"[{citation.index}] {citation.source}{suffix}")
        return "\n".join(lines)
