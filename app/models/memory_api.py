"""Request/response models for the ``/api/v1/memory`` endpoints."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from app.memory.models import MemoryType
class MemoryCreateRequest(BaseModel):
    content: str = Field(..., description="The text to remember")
    type: MemoryType = Field(default=MemoryType.SHORT_TERM)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    user_id: str | None = None
class MemoryItemResponse(BaseModel):
    id: str
    type: MemoryType
    content: str
    tags: list[str]
    metadata: dict
    user_id: str | None
    created_at: datetime
    updated_at: datetime
class MemorySearchResultResponse(BaseModel):
    item: MemoryItemResponse
    score: float
class MemoryListResponse(BaseModel):
    results: list[MemorySearchResultResponse]
    count: int
class MemoryDeleteResponse(BaseModel):
    deleted: bool
    id: str
class MemoryClearResponse(BaseModel):
    cleared: int
