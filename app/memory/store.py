"""Memory storage backends.
``MemoryStore`` is the abstraction that :class:`app.memory.manager.MemoryManager`
depends on. ``LocalMemoryStore`` is a JSON-file-backed MVP implementation.
A future vector-database-backed store only needs to implement the same
interface (see :mod:`app.memory.vector_store` for the prepared extension
point) - the rest of NEXA never needs to change.
"""
from __future__ import annotations
import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from app.memory.models import MemoryItem, MemorySearchResult, MemoryType
class MemoryStore(ABC):
    """Abstract persistence + retrieval interface for memory items."""
    @abstractmethod
    def save(self, item: MemoryItem) -> MemoryItem:
        """Persist ``item`` (insert or update by id) and return it."""
    @abstractmethod
    def get(self, item_id: str) -> MemoryItem | None:
        """Return the item with ``item_id``, or ``None`` if it does not exist."""
    @abstractmethod
    def search(
        self,
        query: str = "",
        type: MemoryType | None = None,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """Return items matching ``query`` (keyword search for the MVP)."""
    @abstractmethod
    def delete(self, item_id: str) -> bool:
        """Delete the item with ``item_id``. Returns ``True`` if it existed."""
    @abstractmethod
    def clear(self, type: MemoryType | None = None) -> int:
        """Delete all items (optionally scoped to ``type``). Returns count removed."""
class LocalMemoryStore(MemoryStore):
    """A simple, dependency-free JSON-file-backed :class:`MemoryStore`.
    Suitable for the MVP / local development. Not intended for concurrent
    multi-process use, but is thread-safe within a single process.
    """
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._items: dict[str, MemoryItem] = {}
        self._load()
    # --- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
                raise ValueError("memory store must contain an 'items' list")
            loaded: dict[str, MemoryItem] = {}
            for entry in raw["items"]:
                item = MemoryItem.model_validate(entry)
                loaded[item.id] = item
        except Exception as exc:
            # A corrupt legacy memory file must never look like an empty store:
            # the next save could otherwise overwrite the only remaining copy.
            raise RuntimeError(
                f"Cannot load NEXA memory store at {self._path}: {exc}"
            ) from exc
        self._items = loaded
    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [item.model_dump(mode="json") for item in self._items.values()]}
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # --- MemoryStore interface --------------------------------------------
    def save(self, item: MemoryItem) -> MemoryItem:
        with self._lock:
            self._items[item.id] = item
            self._flush()
        return item
    def get(self, item_id: str) -> MemoryItem | None:
        with self._lock:
            return self._items.get(item_id)
    def search(
        self,
        query: str = "",
        type: MemoryType | None = None,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        with self._lock:
            candidates = list(self._items.values())
        if type is not None:
            candidates = [i for i in candidates if i.type == type]
        if user_id is not None:
            candidates = [i for i in candidates if i.user_id == user_id]
        query = (query or "").strip().lower()
        if not query:
            scored = [MemorySearchResult(item=i, score=1.0) for i in candidates]
        else:
            terms = query.split()
            scored = []
            for item in candidates:
                haystack = f"{item.content} {' '.join(item.tags)}".lower()
                hits = sum(haystack.count(term) for term in terms)
                if hits > 0:
                    scored.append(MemorySearchResult(item=item, score=float(hits)))
        scored.sort(key=lambda r: (r.score, r.item.updated_at), reverse=True)
        return scored[: max(limit, 0)]
    def delete(self, item_id: str) -> bool:
        with self._lock:
            existed = self._items.pop(item_id, None) is not None
            if existed:
                self._flush()
            return existed
    def clear(self, type: MemoryType | None = None) -> int:
        with self._lock:
            if type is None:
                count = len(self._items)
                self._items.clear()
            else:
                to_remove = [i.id for i in self._items.values() if i.type == type]
                for item_id in to_remove:
                    del self._items[item_id]
                count = len(to_remove)
            self._flush()
            return count
class InMemoryStore(MemoryStore):
    """A process-local, non-persistent :class:`MemoryStore` - handy for tests."""
    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
    def save(self, item: MemoryItem) -> MemoryItem:
        self._items[item.id] = item
        return item
    def get(self, item_id: str) -> MemoryItem | None:
        return self._items.get(item_id)
    def search(
        self,
        query: str = "",
        type: MemoryType | None = None,
        user_id: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        candidates = list(self._items.values())
        if type is not None:
            candidates = [i for i in candidates if i.type == type]
        if user_id is not None:
            candidates = [i for i in candidates if i.user_id == user_id]
        query = (query or "").strip().lower()
        if not query:
            scored = [MemorySearchResult(item=i, score=1.0) for i in candidates]
        else:
            terms = query.split()
            scored = []
            for item in candidates:
                haystack = f"{item.content} {' '.join(item.tags)}".lower()
                hits = sum(haystack.count(term) for term in terms)
                if hits > 0:
                    scored.append(MemorySearchResult(item=item, score=float(hits)))
        scored.sort(key=lambda r: (r.score, r.item.updated_at), reverse=True)
        return scored[: max(limit, 0)]
    def delete(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None
    def clear(self, type: MemoryType | None = None) -> int:
        if type is None:
            count = len(self._items)
            self._items.clear()
            return count
        to_remove = [i.id for i in self._items.values() if i.type == type]
        for item_id in to_remove:
            del self._items[item_id]
        return len(to_remove)
