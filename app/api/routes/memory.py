"""Memory endpoints - a thin HTTP layer over :class:`app.memory.manager.MemoryManager`."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from app.api.deps import get_memory_manager_dep
from app.memory.manager import MemoryManager
from app.memory.models import MemoryType
from app.models.memory_api import (
    MemoryClearResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryItemResponse,
    MemoryListResponse,
    MemorySearchResultResponse,
)
router = APIRouter(prefix="/api/v1/memory", tags=["memory"])
@router.get("", response_model=MemoryListResponse)
async def search_memory(
    query: str = Query(default="", description="Keyword search query"),
    type: MemoryType | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=1000),
    manager: MemoryManager = Depends(get_memory_manager_dep),
) -> MemoryListResponse:
    results = manager.search(query=query, type=type, user_id=user_id, limit=limit)
    payload = [
        MemorySearchResultResponse(item=MemoryItemResponse(**r.item.model_dump()), score=r.score)
        for r in results
    ]
    return MemoryListResponse(results=payload, count=len(payload))
@router.post("", response_model=MemoryItemResponse, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    manager: MemoryManager = Depends(get_memory_manager_dep),
) -> MemoryItemResponse:
    item = manager.save(
        content=request.content,
        type=request.type,
        tags=request.tags,
        metadata=request.metadata,
        user_id=request.user_id,
    )
    return MemoryItemResponse(**item.model_dump())
@router.delete("/{item_id}", response_model=MemoryDeleteResponse)
async def delete_memory_item(
    item_id: str,
    manager: MemoryManager = Depends(get_memory_manager_dep),
) -> MemoryDeleteResponse:
    # Reuse `get` so a missing id surfaces the standard 404 error envelope.
    manager.get(item_id)
    deleted = manager.delete(item_id)
    return MemoryDeleteResponse(deleted=deleted, id=item_id)
@router.delete("", response_model=MemoryClearResponse)
async def clear_memory(
    type: MemoryType | None = Query(default=None),
    manager: MemoryManager = Depends(get_memory_manager_dep),
) -> MemoryClearResponse:
    cleared = manager.clear(type=type)
    return MemoryClearResponse(cleared=cleared)
