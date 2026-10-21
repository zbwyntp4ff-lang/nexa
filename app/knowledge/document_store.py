"""Document metadata store for the Knowledge Base (Part 9).
Separate from the chunk/embedding ``VectorStore`` - this only holds the
lightweight, API-safe :class:`app.knowledge.models.KnowledgeDocument`
records (never full text), mirroring :class:`app.memory.store.LocalMemoryStore`.
"""
from __future__ import annotations
import json
import threading
from pathlib import Path
from app.knowledge.models import KnowledgeDocument
class DocumentStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._documents: dict[str, KnowledgeDocument] = {}
        self._load()
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for entry in raw.get("documents", []):
            doc = KnowledgeDocument.model_validate(entry)
            self._documents[doc.id] = doc
    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"documents": [doc.model_dump(mode="json") for doc in self._documents.values()]}
        self._path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    def save(self, document: KnowledgeDocument) -> KnowledgeDocument:
        with self._lock:
            self._documents[document.id] = document
            self._flush()
        return document
    def get(self, document_id: str) -> KnowledgeDocument | None:
        with self._lock:
            return self._documents.get(document_id)
    def find_by_hash(
        self,
        doc_hash: str,
        project_id: str | None,
        conversation_id: str | None,
        user_id: str | None = None,
    ) -> KnowledgeDocument | None:
        with self._lock:
            for doc in self._documents.values():
                if (
                    doc.doc_hash == doc_hash
                    and doc.project_id == project_id
                    and doc.conversation_id == conversation_id
                    and doc.user_id == user_id
                    and doc.status != "error"
                ):
                    return doc
        return None
    def list(
        self, project_id: str | None = None, user_id: str | None = None
    ) -> list[KnowledgeDocument]:
        with self._lock:
            docs = list(self._documents.values())
        if user_id is not None:
            docs = [d for d in docs if d.user_id == user_id]
        if project_id is not None:
            docs = [d for d in docs if d.project_id == project_id]
        return sorted(docs, key=lambda d: d.created_at, reverse=True)
    def delete(self, document_id: str) -> bool:
        with self._lock:
            existed = self._documents.pop(document_id, None) is not None
            if existed:
                self._flush()
            return existed
    def delete_user(self, user_id: str) -> list[str]:
        """Remove all documents for ``user_id``. Returns deleted document ids."""
        with self._lock:
            to_remove = [d.id for d in self._documents.values() if d.user_id == user_id]
            for doc_id in to_remove:
                del self._documents[doc_id]
            if to_remove:
                self._flush()
            return to_remove
class InMemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._documents: dict[str, KnowledgeDocument] = {}
    def _flush(self) -> None:
        return None
