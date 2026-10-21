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
    replace_id: str | None = Field(
        default=None,
        description="If set after a contradiction warning, replace this item instead of creating a duplicate.",
    )
    force: bool = Field(
        default=False,
        description="Save even when contradictions are detected (still does not auto-delete old rows).",
    )


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    type: MemoryType | None = None
    tags: list[str] | None = None
    metadata: dict | None = None


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


class MemoryContradiction(BaseModel):
    existing_id: str
    existing_content: str
    new_content: str
    reason: str


class MemoryCreateResponse(BaseModel):
    item: MemoryItemResponse | None = None
    contradictions: list[MemoryContradiction] = Field(default_factory=list)
    saved: bool = True


class MemoryDeleteResponse(BaseModel):
    deleted: bool
    id: str


class MemoryClearResponse(BaseModel):
    cleared: int
