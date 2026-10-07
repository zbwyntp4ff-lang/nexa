"""Data models for the NEXA web research subsystem."""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
class SearchResult(BaseModel):
    """A single organic search result."""
    title: str
    url: str
    snippet: str = ""
    source: str
    timestamp: datetime = Field(default_factory=_utcnow)
class PageDocument(BaseModel):
    """The extracted content of a fetched web page."""
    url: str
    title: str = ""
    text: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)
    content_hash: str
