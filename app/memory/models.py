"""Data models for the NEXA memory subsystem."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
class MemoryType(str, Enum):
    """The four memory scopes required by NEXA Part 2."""
    SHORT_TERM = "short_term"
    CONVERSATION = "conversation"
    LONG_TERM = "long_term"
    USER_PREFERENCE = "user_preference"
def _new_id() -> str:
    return uuid.uuid4().hex
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
class MemoryItem(BaseModel):
    """A single unit of stored memory.
    ``content`` is always plain text. Callers must never put secrets (API
    keys, passwords, tokens) into ``content`` or ``metadata`` -
    :class:`app.memory.manager.MemoryManager` enforces this at write time.
    """
    id: str = Field(default_factory=_new_id)
    type: MemoryType
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    user_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
class MemorySearchResult(BaseModel):
    """A memory item paired with a naive relevance score."""
    item: MemoryItem
    score: float
