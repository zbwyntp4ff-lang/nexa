"""Chunking and naive lexical retrieval for the document pipeline.
No embeddings or vector store are used here (Part 8 scope): chunks are fixed
by character count, and the "most relevant" ones for a query are picked by
simple keyword overlap. This is retrieval plumbing, not a model quality
ranking - it never compares AI models to each other.
"""
from __future__ import annotations
import re
DEFAULT_CHUNK_SIZE = 1_800
DEFAULT_CHUNK_OVERLAP = 200
_WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)
def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split ``text`` into overlapping fixed-size chunks."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks
def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _WORD_PATTERN.findall(text) if len(token) > 2}
def select_relevant_chunks(chunks: list[str], query: str, max_chars: int) -> list[str]:
    """Pick chunks most likely relevant to ``query``, bounded by ``max_chars``.
    Falls back to the first chunks (in document order) when there is no
    query or no lexical overlap, so the model still gets *some* context
    rather than nothing.
    """
    if not chunks:
        return []
    query_tokens = _tokens(query)
    if query_tokens:
        scored = sorted(
            range(len(chunks)),
            key=lambda i: len(query_tokens & _tokens(chunks[i])),
            reverse=True,
        )
    else:
        scored = list(range(len(chunks)))
    selected: list[str] = []
    used_chars = 0
    for index in scored:
        chunk = chunks[index]
        if used_chars >= max_chars:
            break
        remaining = max_chars - used_chars
        piece = chunk if len(chunk) <= remaining else chunk[:remaining]
        selected.append(piece)
        used_chars += len(piece)
    return selected
