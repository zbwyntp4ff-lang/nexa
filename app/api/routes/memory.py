"""Memory endpoints - a thin HTTP layer over :class:`app.memory.manager.MemoryManager`."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_memory_manager_dep
from app.api.security_deps import require_user, require_user_when_enforced
from app.auth.models import UserRecord
from app.learning.contradictions import find_contradictions
from app.memory.manager import MemoryManager
from app.memory.models import MemoryType
from app.models.memory_api import (
    MemoryClearResponse,
    MemoryContradiction,
    MemoryCreateRequest,
    MemoryCreateResponse,
    MemoryDeleteResponse,
    MemoryItemResponse,
    MemoryListResponse,
    MemorySearchResultResponse,
    MemoryUpdateRequest,
)

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("", response_model=MemoryListResponse)
async def search_memory(
    query: str = Query(default="", description="Keyword search query"),
    type: MemoryType | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=1000),
    manager: MemoryManager = Depends(get_memory_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> MemoryListResponse:
    # Ignore client-supplied user_id when authenticated — scope to the session user.
    scoped = user.id if user is not None else user_id
    results = manager.search(query=query, type=type, user_id=scoped, limit=limit)
    payload = [
        MemorySearchResultResponse(item=MemoryItemResponse(**r.item.model_dump()), score=r.score)
        for r in results
    ]
    return MemoryListResponse(results=payload, count=len(payload))


@router.post("", response_model=MemoryCreateResponse, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    manager: MemoryManager = Depends(get_memory_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> MemoryCreateResponse:
    scoped = user.id if user is not None else request.user_id
    conflicts = find_contradictions(
        manager, user_id=scoped, content=request.content, type=request.type
    )
    if conflicts and not request.force and not request.replace_id:
        return MemoryCreateResponse(
            item=None,
            saved=False,
            contradictions=[
                MemoryContradiction(
                    existing_id=c.existing_id,
                    existing_content=c.existing_content,
                    new_content=c.new_content,
                    reason=c.reason,
                )
                for c in conflicts
            ],
        )
    if request.replace_id:
        manager.delete(request.replace_id, user_id=scoped)
    item = manager.save(
        content=request.content,
        type=request.type,
        tags=request.tags,
        metadata={
            **(request.metadata or {}),
            "status": "confirmed",
            "source": (request.metadata or {}).get("source", "user"),
        },
        user_id=scoped,
    )
    return MemoryCreateResponse(
        item=MemoryItemResponse(**item.model_dump()),
        saved=True,
        contradictions=[
            MemoryContradiction(
                existing_id=c.existing_id,
                existing_content=c.existing_content,
                new_content=c.new_content,
                reason=c.reason,
            )
            for c in conflicts
        ],
    )


def _owned_or_404(manager: MemoryManager, item_id: str, user: UserRecord | None):
    item = manager.get(item_id)
    if user is not None and item.user_id not in (None, user.id):
        from app.models.errors import MemoryItemNotFoundError

        raise MemoryItemNotFoundError(item_id)
    return item


@router.patch("/{item_id}", response_model=MemoryItemResponse)
async def update_memory(
    item_id: str,
    request: MemoryUpdateRequest,
    manager: MemoryManager = Depends(get_memory_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> MemoryItemResponse:
    scoped = user.id if user is not None else None
    _owned_or_404(manager, item_id, user)
    item = manager.update(
        item_id,
        content=request.content,
        type=request.type,
        tags=request.tags,
        metadata=request.metadata,
        user_id=scoped,
    )
    return MemoryItemResponse(**item.model_dump())


@router.delete("/{item_id}", response_model=MemoryDeleteResponse)
async def delete_memory_item(
    item_id: str,
    manager: MemoryManager = Depends(get_memory_manager_dep),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> MemoryDeleteResponse:
    scoped = user.id if user is not None else None
    _owned_or_404(manager, item_id, user)
    deleted = manager.delete(item_id, user_id=scoped)
    return MemoryDeleteResponse(deleted=deleted, id=item_id)


@router.delete("", response_model=MemoryClearResponse)
async def clear_memory(
    user: Annotated[UserRecord, Depends(require_user)],
    type: MemoryType | None = Query(default=None),
    manager: MemoryManager = Depends(get_memory_manager_dep),
) -> MemoryClearResponse:
    # Clearing is destructive: unlike local search/add in dev mode, it must
    # always be scoped to an authenticated account and can never clear all users.
    cleared = manager.clear(type=type, user_id=user.id)
    return MemoryClearResponse(cleared=cleared)
