"""Forward-looking interface for a future vector-database-backed memory store.
Nothing in this module is used by NEXA yet - it exists so that swapping
:class:`app.memory.store.LocalMemoryStore` for a real vector database later
is a drop-in change: implement :class:`VectorMemoryStore` and register it in
place of ``LocalMemoryStore`` wherever a ``MemoryStore`` is constructed
(e.g. :func:`app.memory.manager.get_memory_manager`).
"""
from __future__ import annotations
from abc import abstractmethod
from app.memory.store import MemoryStore
class Embedder:
    """Turns text into an embedding vector. To be implemented in a later part."""
    @abstractmethod
    def embed(self, text: str) -> list[float]:  # pragma: no cover - future work
        raise NotImplementedError
class VectorMemoryStore(MemoryStore):
    """A :class:`MemoryStore` that retrieves items by semantic similarity.
    Concrete implementations (e.g. backed by Chroma, pgvector, Pinecone, ...)
    should:
    1. Compute an embedding for ``item.content`` via an :class:`Embedder`
       when saving.
    2. Implement :meth:`similarity_search` to run a nearest-neighbor query.
    3. Implement the base :class:`MemoryStore` methods (``save``, ``get``,
       ``search``, ``delete``, ``clear``), where ``search`` delegates to
       :meth:`similarity_search` instead of keyword matching.
    This class intentionally raises ``NotImplementedError`` everywhere - it
    is a prepared extension point for a future part of the project, not a
    usable backend today.
    """
    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
    @abstractmethod
    def similarity_search(
        self, query_vector: list[float], limit: int = 10
    ) -> list[tuple[str, float]]:
        """Return ``(item_id, similarity_score)`` pairs, most similar first."""
        raise NotImplementedError(
            "VectorMemoryStore is a future extension point and has no "
            "concrete implementation yet."
        )
    def save(self, item):  # noqa: D102
        raise NotImplementedError("Vector-backed memory storage is not implemented yet.")
    def get(self, item_id):  # noqa: D102
        raise NotImplementedError("Vector-backed memory storage is not implemented yet.")
    def search(self, query="", type=None, user_id=None, limit=10):  # noqa: D102
        raise NotImplementedError("Vector-backed memory storage is not implemented yet.")
    def delete(self, item_id):  # noqa: D102
        raise NotImplementedError("Vector-backed memory storage is not implemented yet.")
    def clear(self, type=None):  # noqa: D102
        raise NotImplementedError("Vector-backed memory storage is not implemented yet.")
