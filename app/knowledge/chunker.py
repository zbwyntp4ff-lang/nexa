"""``DocumentChunker`` (Part 9).
Reuses the existing character-based chunker from
:mod:`app.attachments.chunking` (Part 8) rather than duplicating chunking
logic - only the size/overlap defaults are Knowledge-Base-specific.
"""
from __future__ import annotations
from app.attachments.chunking import chunk_text
DEFAULT_CHUNK_SIZE_CHARS = 1_500
DEFAULT_CHUNK_OVERLAP_CHARS = 150
class DocumentChunker:
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
        overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
        max_chunks: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_chunks = max_chunks
    def split(self, text: str) -> list[str]:
        chunks = chunk_text(text, chunk_size=self.chunk_size, overlap=self.overlap)
        if self.max_chunks is not None and len(chunks) > self.max_chunks:
            chunks = chunks[: self.max_chunks]
        return chunks
