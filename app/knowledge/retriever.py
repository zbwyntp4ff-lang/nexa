"""``Retriever`` - semantic search + context assembly (Part 9).
``User query -> embed -> vector search -> filter by score/scope -> bounded
context``. Never returns the whole Knowledge Base - only the top-k chunks
above a similarity threshold, truncated to a configured character budget.
"""
from __future__ import annotations
from app.core.logging_config import get_logger
from app.knowledge.embeddings import EmbeddingProvider, _tokenize
from app.knowledge.models import Citation, RetrievalResult, RetrievedChunk
from app.knowledge.vector_store import VectorStore
logger = get_logger("nexa.knowledge.retriever")
DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.28
DEFAULT_MAX_CONTEXT_CHARS = 6_000


def _token_overlap(query: str, text: str) -> int:
    """Count shared tokens (len>2) — filters hashing-embedding false positives."""
    q = {t for t in _tokenize(query) if len(t) > 2}
    if not q:
        return 0
    d = {t for t in _tokenize(text) if len(t) > 2}
    return len(q & d)
class Retriever:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    ) -> None:
        self._vector_store = vector_store
        self._embeddings = embedding_provider
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.max_context_chars = max_context_chars
    def retrieve(
        self,
        query: str,
        *,
        project_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        max_context_chars: int | None = None,
    ) -> RetrievalResult:
        """Run the full retrieval step for ``query`` and return bounded, scoped context.
        Never sends the whole Knowledge Base anywhere - only chunks scoring
        above ``similarity_threshold``, capped at ``top_k`` and at
        ``max_context_chars`` total characters.
        """
        k = top_k if top_k is not None else self.top_k
        threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
        budget = max_context_chars if max_context_chars is not None else self.max_context_chars
        logger.info(
            "retrieval_started query_len=%d project_id=%s user_id=%s",
            len(query),
            project_id or "-",
            "set" if user_id else "-",
        )
        query_vector = self._embeddings.embed(query)
        # Over-fetch a little so the score/threshold filter still leaves us
        # up to `k` results even if some higher-ranked candidates are cut.
        raw = self._vector_store.search(
            query_vector,
            top_k=max(k * 2, k),
            project_id=project_id,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        filtered = [
            (chunk, score)
            for chunk, score in raw
            if score >= threshold and _token_overlap(query, chunk.text) >= 1
        ][:k]
        if not filtered:
            logger.info("retrieval_completed matches=0")
            return RetrievalResult(chunks=[], citations=[], context_text="", insufficient=True)
        retrieved: list[RetrievedChunk] = []
        used_chars = 0
        parts: list[str] = []
        citations: list[Citation] = []
        for index, (chunk, score) in enumerate(filtered, start=1):
            if used_chars >= budget:
                break
            separator_len = 2 if parts else 0  # "\n\n" joins parts together
            prefix = f"[{index}] "
            remaining = budget - used_chars - separator_len - len(prefix)
            if remaining <= 0:
                break
            text = chunk.text if len(chunk.text) <= remaining else chunk.text[:remaining]
            piece = f"{prefix}{text}"
            used_chars += len(piece) + separator_len
            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    # Resolved to the real filename/source by CitationManager,
                    # which has access to document metadata; kept as a safe
                    # fallback here since the Retriever only knows chunks.
                    filename=chunk.document_id,
                    source=chunk.document_id,
                    text=text,
                    score=round(score, 4),
                    page=chunk.page,
                    section=chunk.section,
                )
            )
            parts.append(piece)
        logger.info("retrieval_completed matches=%d chars=%d", len(retrieved), used_chars)
        return RetrievalResult(
            chunks=retrieved,
            citations=citations,  # filled in by CitationManager, which knows document metadata
            context_text="\n\n".join(parts),
            insufficient=False,
        )
