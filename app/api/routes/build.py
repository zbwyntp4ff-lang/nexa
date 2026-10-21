"""BUILD_PROJECT API — create/edit real projects and serve preview files."""
from __future__ import annotations

import io
import mimetypes
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.build.engine import BuildEngine, resolve_preview_file
from app.build.evaluation import evaluate_project, evaluation_to_public, load_project_files
from app.build.events import recent_events
from app.build.intents import is_build_request
from app.build.models import BuildProjectRecord, BuildRunRequest, BuildRunResponse
from app.build import store
from app.config.settings import get_settings
from app.core.logging_config import get_logger

logger = get_logger("nexa.api.build")
router = APIRouter(prefix="/api/v1", tags=["build"])
_Auth = Annotated[UserRecord | None, Depends(require_user_when_enforced)]


# Preview CSP: scripts from self + Three.js CDN hosts only (Part 13).
_PREVIEW_CSP = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors *; "
    "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src https://cdn.jsdelivr.net https://unpkg.com; "
    "media-src 'self' blob:; "
    "worker-src 'self' blob:; "
    "child-src 'none'; "
    "object-src 'none'"
)


def _preview_headers() -> dict[str, str]:
    return {
        "Content-Security-Policy": _PREVIEW_CSP,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


def _require_build_access(record: BuildProjectRecord | None, user: UserRecord | None) -> BuildProjectRecord:
    """Enforce ownership when TOKENS_ENFORCE is on. Never leak existence via 403."""
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")
    settings = get_settings()
    if not settings.tokens_enforce:
        return record
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not record.user_id or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return record


@router.post("/build/detect")
async def detect_build(body: dict, _user: _Auth = None) -> dict:
    message = str(body.get("message") or "")
    conversation_id = body.get("conversation_id")
    has_project = store.get_project_for_conversation(conversation_id) is not None
    matched = is_build_request(message, has_active_project=has_project)
    return {"matched": matched, "intent": "BUILD_PROJECT" if matched else None}


@router.post("/build/run", response_model=BuildRunResponse)
async def run_build(body: BuildRunRequest, user: _Auth = None) -> BuildRunResponse:
    if body.project_id:
        existing = store.get_project(body.project_id)
        _require_build_access(existing, user)
    engine = BuildEngine()
    result = await engine.run(
        body.message,
        conversation_id=body.conversation_id,
        project_id=body.project_id,
        user_id=user.id if user is not None else None,
    )
    logger.info(
        "build run success=%s mode=%s project=%s",
        result.success,
        result.mode,
        result.project_id,
    )
    return result


@router.get("/build/projects")
async def list_build_projects(user: _Auth = None) -> dict:
    settings = get_settings()
    projects = store.list_projects()
    if settings.tokens_enforce:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        projects = [p for p in projects if p.user_id == user.id]
    # Never return workspace filesystem paths beyond root_rel already on record.
    public = [
        {
            "project_id": p.project_id,
            "slug": p.slug,
            "title": p.title,
            "status": p.status,
            "preview_url": p.preview_url,
            "stack": p.stack,
            "entry_file": p.entry_file,
        }
        for p in projects
    ]
    return {"projects": public, "count": len(public)}


@router.get("/build/projects/{project_id}")
async def get_build_project(project_id: str, user: _Auth = None) -> dict:
    record = _require_build_access(store.get_project(project_id), user)
    return {
        "project_id": record.project_id,
        "slug": record.slug,
        "title": record.title,
        "status": record.status,
        "entry_file": record.entry_file,
        "files": list(record.files),
        "preview_url": record.preview_url,
        "stack": record.stack,
        "features": list(record.features or []),
        "root_rel": record.root_rel,
    }


@router.get("/build/events")
async def list_build_events(
    project_id: str | None = None, limit: int = 50, user: _Auth = None
) -> dict:
    """Observability: real Build Events emitted by the engine (ring buffer)."""
    if project_id:
        _require_build_access(store.get_project(project_id), user)
    elif get_settings().tokens_enforce:
        # Global event dump would leak other users' project activity.
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"events": [], "count": 0, "note": "project_id required when TOKENS_ENFORCE"}
    items = recent_events(project_id=project_id, limit=min(limit, 200))
    return {"events": [e.model_dump() for e in items], "count": len(items)}


@router.post("/build/evaluate")
async def evaluate_build_project(body: dict, user: _Auth = None) -> dict:
    """Re-evaluate an existing BUILD_PROJECT workspace against a request."""
    project_id = str(body.get("project_id") or "")
    message = str(body.get("message") or "")
    record = _require_build_access(store.get_project(project_id), user)
    root = store.workspace_root() / record.root_rel
    files = load_project_files(root, list(record.files))
    preview_ok = resolve_preview_file(project_id, record.entry_file) is not None
    plan = record.plan
    if plan is None:
        raise HTTPException(status_code=400, detail="Project has no BuildPlan")
    settings = get_settings()
    result = evaluate_project(
        user_request=message or plan.goal,
        plan=plan,
        files=files,
        preview_ok=preview_ok,
        tests_passed=record.status in {"READY", "TESTING", "IMPROVING"},
        pass_threshold=settings.build_eval_pass_threshold,
    )
    return {"project_id": project_id, "evaluation": evaluation_to_public(result)}


@router.get("/build/preview/{project_id}/{file_path:path}")
async def preview_file(project_id: str, file_path: str, user: _Auth = None) -> FileResponse:
    record = store.get_project(project_id)
    _require_build_access(record, user)
    target = resolve_preview_file(project_id, file_path)
    if target is None:
        raise HTTPException(status_code=404, detail="Preview file not found")
    media, _ = mimetypes.guess_type(str(target))
    return FileResponse(
        target,
        media_type=media or "application/octet-stream",
        headers=_preview_headers(),
    )


@router.get("/build/export/{project_id}")
async def export_build_project(project_id: str, user: _Auth = None) -> StreamingResponse:
    """Download project workspace as a zip (Part 13 Game Creator export)."""
    record = _require_build_access(store.get_project(project_id), user)
    root = (store.workspace_root() / record.root_rel).resolve()
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Project workspace missing")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if ".." in rel.split("/"):
                continue
            zf.write(path, arcname=rel)
    buf.seek(0)
    filename = f"{record.slug or project_id}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
