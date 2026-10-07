"""Data models for the Knowledge Base (Part 9).
Nothing here ever carries raw file bytes or full document text over the
API - only bounded metadata/previews (mirrors :mod:`app.attachments.models`).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
def _new_id() -> str:
    return uuid.uuid4().hex
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
class KnowledgeSourceType(str, Enum):
    """Where a document's content came from."""
    UPLOAD = "upload"
    DESKTOP_FILE = "desktop_file"
    WEB_RESEARCH = "web_research"
    NOTE = "note"
class KnowledgeStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
class KnowledgeDocument(BaseModel):
    """Public metadata for one indexed document. Never includes full text."""
    id: str = Field(default_factory=_new_id)
    filename: str
    source_type: KnowledgeSourceType
    source: str  # original path/URL/title, for display and citations
    format: str
    size_bytes: int
    status: KnowledgeStatus = KnowledgeStatus.PROCESSING
    error: str | None = None
    chunk_count: int = 0
    project_id: str | None = None
    conversation_id: str | None = None
    doc_hash: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
class KnowledgeChunk(BaseModel):
    """One indexed chunk of a document, with its embedding vector."""
    id: str = Field(default_factory=_new_id)
    document_id: str
    text: str
    embedding: list[float] = Field(default_factory=list)
    chunk_index: int = 0
    page: int | None = None
    section: str | None = None
    project_id: str | None = None
    conversation_id: str | None = None
class RetrievedChunk(BaseModel):
    """One chunk returned by :class:`app.knowledge.retriever.Retriever`."""
    chunk_id: str
    document_id: str
    filename: str
    source: str
    text: str
    score: float
    page: int | None = None
    section: str | None = None
class Citation(BaseModel):
    """A source reference attached to a generated answer."""
    index: int
    document_id: str
    filename: str
    source: str
    page: int | None = None
    section: str | None = None
class RetrievalResult(BaseModel):
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    context_text: str = ""
    insufficient: bool = True
