"""``MemoryManager`` - the model-agnostic façade over a :class:`MemoryStore`.
Nothing here depends on any :class:`app.providers.base.AIProvider`. Any part
of NEXA (NexaCore, the Agent, the API layer) can use ``MemoryManager``
without caring which provider generated the content being remembered.
"""
from __future__ import annotations
from functools import lru_cache
from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root
from app.core.secrets import contains_secret, is_secret_field_name
from app.memory.models import MemoryItem, MemorySearchResult, MemoryType
from app.memory.store import LocalMemoryStore, MemoryStore
from app.models.errors import MemoryItemNotFoundError, SecretInMemoryError
class MemoryManager:
    """Save/search/get/delete/clear memory, independent of any AI provider."""
    def __init__(self, store: MemoryStore, default_search_limit: int = 10) -> None:
        self._store = store
        self._default_search_limit = default_search_limit
    # --- guardrails --------------------------------------------------------
    @staticmethod
    def _assert_no_secrets(content: str, metadata: dict | None) -> None:
        if contains_secret(content):
            raise SecretInMemoryError()
        for key, value in (metadata or {}).items():
            if is_secret_field_name(str(key)):
                raise SecretInMemoryError()
            if isinstance(value, str) and contains_secret(value):
                raise SecretInMemoryError()
    # --- core CRUD -----------------------------------------------------------
    def save(
        self,
        content: str,
        type: MemoryType = MemoryType.SHORT_TERM,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        user_id: str | None = None,
    ) -> MemoryItem:
        """Validate, then persist a new memory item.
        Raises:
            app.models.errors.SecretInMemoryError: If ``content`` or
                ``metadata`` looks like it contains an API key, password, or
                other secret.
        """
        self._assert_no_secrets(content, metadata)
        item = MemoryItem(
            type=type,
            content=content,
            tags=tags or [],
            metadata=metadata or {},
            user_id=user_id,
        )
        return self._store.save(item)
    def get(self, item_id: str) -> MemoryItem:
        """Return the memory item with ``item_id``.
        Raises:
            app.models.errors.MemoryItemNotFoundError: If no such item exists.
        """
        item = self._store.get(item_id)
        if item is None:
            raise MemoryItemNotFoundError(item_id)
        return item
    def search(
        self,
        query: str = "",
        type: MemoryType | None = None,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> list[MemorySearchResult]:
        """Keyword-search memory items. Returns highest-scoring first."""
        return self._store.search(
            query=query,
            type=type,
            user_id=user_id,
            limit=limit if limit is not None else self._default_search_limit,
        )
    def delete(self, item_id: str, *, user_id: str | None = None) -> bool:
        """Delete a memory item by id. Returns ``True`` if it existed.

        When ``user_id`` is provided, only delete records owned by that
        exact user. Ownerless legacy records remain in the local namespace.
        """
        item = self._store.get(item_id)
        if item is None:
            return False
        if user_id is not None and item.user_id != user_id:
            raise MemoryItemNotFoundError(item_id)
        return self._store.delete(item_id)

    def update(
        self,
        item_id: str,
        *,
        content: str | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        type: MemoryType | None = None,
        user_id: str | None = None,
    ) -> MemoryItem:
        """Update an existing item; re-check secrets; preserve id/created_at."""
        from datetime import datetime, timezone

        item = self.get(item_id)
        if user_id is not None and item.user_id != user_id:
            raise MemoryItemNotFoundError(item_id)
        new_content = content if content is not None else item.content
        new_meta = metadata if metadata is not None else item.metadata
        self._assert_no_secrets(new_content, new_meta)
        updated = item.model_copy(
            update={
                "content": new_content,
                "tags": tags if tags is not None else item.tags,
                "metadata": new_meta,
                "type": type if type is not None else item.type,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self._store.save(updated)

    def clear(self, type: MemoryType | None = None, *, user_id: str | None = None) -> int:
        """Delete memory items (optionally scoped to ``type`` and/or ``user_id``)."""
        if user_id is None:
            return self._store.clear(type=type)
        clear_user = getattr(self._store, "clear_user", None)
        if callable(clear_user):
            return int(clear_user(user_id, type))
        results = self.search(query="", type=type, user_id=user_id, limit=10000)
        count = 0
        for hit in results:
            if self._store.delete(hit.item.id):
                count += 1
        return count

    def clear_for_user(self, user_id: str) -> int:
        """Delete all memory belonging to ``user_id``."""
        return self.clear(user_id=user_id)
    # --- convenience helpers ------------------------------------------------
    def remember_turn(self, role: str, content: str, conversation_id: str | None = None) -> MemoryItem:
        """Store one conversation turn as :data:`MemoryType.CONVERSATION`."""
        return self.save(
            content=content,
            type=MemoryType.CONVERSATION,
            tags=[role],
            metadata={"role": role, "conversation_id": conversation_id} if conversation_id else {"role": role},
        )
    def set_preference(self, key: str, value: str, user_id: str | None = None) -> MemoryItem:
        """Store a user preference as :data:`MemoryType.USER_PREFERENCE`."""
        return self.save(
            content=value,
            type=MemoryType.USER_PREFERENCE,
            tags=[key],
            metadata={"preference_key": key},
            user_id=user_id,
        )
    def get_preference(self, key: str, user_id: str | None = None) -> str | None:
        """Return the most recent value stored for preference ``key``, if any."""
        results = self.search(query="", type=MemoryType.USER_PREFERENCE, user_id=user_id, limit=1000)
        matching = [r.item for r in results if r.item.metadata.get("preference_key") == key]
        if not matching:
            return None
        latest = max(matching, key=lambda i: i.updated_at)
        return latest.content
@lru_cache
def get_memory_manager() -> MemoryManager:
    """Return a process-wide cached :class:`MemoryManager`.
    Tests that need isolation should call ``get_memory_manager.cache_clear()``
    or construct a ``MemoryManager`` directly with an
    :class:`app.memory.store.InMemoryStore`.

    Backend: ``MEMORY_BACKEND=sql`` (default) uses ``DATABASE_URL``;
    ``MEMORY_BACKEND=json`` keeps the legacy file store.
    """
    settings = get_settings()
    backend = (getattr(settings, "memory_backend", None) or "sql").strip().lower()
    if backend == "json":
        store = LocalMemoryStore(resolve_under_project_root(settings.memory_store_path))
    else:
        from app.db.engine import get_database
        from app.memory.sql_store import SqlMemoryStore

        get_database().migrate()
        store = SqlMemoryStore(get_database())
    return MemoryManager(store, default_search_limit=settings.memory_search_limit)
