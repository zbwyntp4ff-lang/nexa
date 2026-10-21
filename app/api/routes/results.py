"""Secure download of agent-generated office files (by file_id only)."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root
from app.tools.office.result_store import ResultStore
from app.tools.registry import get_default_tool_registry

router = APIRouter(prefix="/api/v1/results", tags=["results"])
_Auth = Annotated[UserRecord | None, Depends(require_user_when_enforced)]


class ResultMetaResponse(BaseModel):
    file_id: str
    filename: str
    media_type: str
    size_bytes: int
    download_url: str
    task_id: str
    tool_name: str | None = None
    created_at: str


@lru_cache
def get_result_store() -> ResultStore:
    registry = get_default_tool_registry()
    store = getattr(registry, "_result_store", None)
    if isinstance(store, ResultStore):
        return store
    root = resolve_under_project_root(get_settings().agent_workspace_dir)
    return ResultStore(root)


def _resolve_result(file_id: str, user: UserRecord | None):
    store = get_result_store()
    uid = user.id if user else None
    rec = store.get(file_id, user_id=uid)
    if rec is None:
        raise HTTPException(status_code=404, detail="Result file not found or access denied.")
    path = store.absolute_path(file_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Result file missing on disk.")
    return rec, path


@router.get("/{file_id}", response_model=ResultMetaResponse)
async def get_result_meta(file_id: str, user: _Auth = None) -> ResultMetaResponse:
    rec, _path = _resolve_result(file_id, user)
    return ResultMetaResponse(
        file_id=rec.file_id,
        filename=rec.filename,
        media_type=rec.media_type,
        size_bytes=rec.size_bytes,
        download_url=rec.download_path,
        task_id=rec.task_id,
        tool_name=rec.tool_name,
        created_at=rec.created_at,
    )


@router.get("/{file_id}/download")
async def download_result(file_id: str, user: _Auth = None) -> FileResponse:
    rec, path = _resolve_result(file_id, user)
    return FileResponse(
        path=path,
        media_type=rec.media_type,
        filename=rec.filename,
        content_disposition_type="attachment",
    )
