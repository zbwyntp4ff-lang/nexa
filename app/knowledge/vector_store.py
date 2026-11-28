"""``VectorStore`` interface + local implementation (Part 9).
Mirrors :class:`app.memory.store.MemoryStore`'s pattern: an abstract
interface so a real vector database can be swapped in later without
touching :class:`app.knowledge.knowledge_base.KnowledgeBase` or anything
above it, and a dependency-free JSON-backed local implementation for now.
The whole index is loaded into memory once at construction (not re-read
from disk on every search), and chunks/documents are removed together so a
deleted document's vectors never linger.
"""
from __future__ import annotations
import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from app.knowledge.embeddings import cosine_similarity
from app.knowledge.models import KnowledgeChunk
class VectorStore(ABC):
    """Abstract persistence + similarity-search interface for chunks."""
    @abstractmethod
    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        """Persist ``chunks`` (each carrying its own embedding vector)."""
    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        project_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> list[tuple[KnowledgeChunk, float]]:
        """Return the ``top_k`` most similar chunks (scoped) with their scores."""
    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Delete every chunk belonging to ``document_id``. Returns count removed."""
    @abstractmethod
    def chunk_count(self, document_id: str | None = None) -> int:
        """Return the number of stored chunks (optionally for one document)."""
    def delete_user(self, user_id: str) -> int:
        """Delete every chunk owned by ``user_id``. Default: unsupported."""
        raise NotImplementedError
def _visible(
    chunk: KnowledgeChunk,
    project_id: str | None,
    conversation_id: str | None,
    user_id: str | None = None,
) -> bool:
    """Project/conversation scoped chunks are only visible to a matching request.
    When ``user_id`` is set, only that user's chunks (and legacy null-owner rows
    are **not** shared across users in cloud mode — null owner is visible only
    when the caller also has no user_id, e.g. single-user desktop).
    """
    if user_id is not None:
        if chunk.user_id != user_id:
            return False
    if chunk.project_id is not None and chunk.project_id != project_id:
        return False
    if chunk.conversation_id is not None and chunk.conversation_id != conversation_id:
        return False
    return True
class LocalVectorStore(VectorStore):
    """A simple, dependency-free JSON-file-backed :class:`VectorStore`.
    Brute-force cosine similarity over the in-memory index - appropriate for
    a local/single-user Knowledge Base; a real vector database only needs to
    implement this same interface to replace it.
    """
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._chunks: dict[str, KnowledgeChunk] = {}
        self._load()
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("chunks"), list):
                raise ValueError("vector store must contain a 'chunks' list")
            loaded: dict[str, KnowledgeChunk] = {}
            for entry in raw["chunks"]:
                chunk = KnowledgeChunk.model_validate(entry)
                loaded[chunk.id] = chunk
        except Exception as exc:  # noqa: BLE001 - never replace a corrupt index with empty state
            raise RuntimeError(
                f"Cannot load NEXA knowledge vector store at {self._path}: {exc}"
            ) from exc
        self._chunks = loaded
    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"chunks": [chunk.model_dump(mode="json") for chunk in self._chunks.values()]}
        self._path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        with self._lock:
            for chunk in chunks:
                self._chunks[chunk.id] = chunk
            self._flush()
    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        project_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> list[tuple[KnowledgeChunk, float]]:
        with self._lock:
            candidates = list(self._chunks.values())
        scored = [
            (chunk, cosine_similarity(query_vector, chunk.embedding))
            for chunk in candidates
            if _visible(chunk, project_id, conversation_id, user_id)
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[: max(top_k, 0)]
    def delete_document(self, document_id: str) -> int:
        with self._lock:
            to_remove = [cid for cid, chunk in self._chunks.items() if chunk.document_id == document_id]
            for cid in to_remove:
                del self._chunks[cid]
            if to_remove:
                self._flush()
            return len(to_remove)
    def delete_user(self, user_id: str) -> int:
        with self._lock:
            to_remove = [cid for cid, chunk in self._chunks.items() if chunk.user_id == user_id]
            for cid in to_remove:
                del self._chunks[cid]
            if to_remove:
                self._flush()
            return len(to_remove)
    def chunk_count(self, document_id: str | None = None) -> int:
        with self._lock:
            if document_id is None:
                return len(self._chunks)
            return sum(1 for chunk in self._chunks.values() if chunk.document_id == document_id)
class InMemoryVectorStore(LocalVectorStore):
    """A process-local, non-persistent store - handy for tests."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chunks: dict[str, KnowledgeChunk] = {}
    def _flush(self) -> None:  # never touches disk
        return None
