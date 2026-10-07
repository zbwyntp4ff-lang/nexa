"""BUILD_PROJECT API — create/edit real projects and serve preview files."""
from __future__ import annotations

import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.build.engine import BuildEngine, resolve_preview_file
from app.build.evaluation import evaluate_project, evaluation_to_public, load_project_files
from app.build.events import recent_events
from app.build.intents import is_build_request
from app.build.models import BuildRunRequest, BuildRunResponse
from app.build import store
from app.config.settings import get_settings
from app.core.logging_config import get_logger

logger = get_logger("nexa.api.build")
router = APIRouter(prefix="/api/v1", tags=["build"])


@router.post("/build/detect")
async def detect_build(body: dict) -> dict:
    message = str(body.get("message") or "")
    conversation_id = body.get("conversation_id")
    has_project = store.get_project_for_conversation(conversation_id) is not None
    matched = is_build_request(message, has_active_project=has_project)
    return {"matched": matched, "intent": "BUILD_PROJECT" if matched else None}


@router.post("/build/run", response_model=BuildRunResponse)
async def run_build(body: BuildRunRequest) -> BuildRunResponse:
    engine = BuildEngine()
    result = await engine.run(
        body.message,
        conversation_id=body.conversation_id,
        project_id=body.project_id,
    )
    logger.info(
        "build run success=%s mode=%s project=%s",
        result.success,
        result.mode,
        result.project_id,
    )
    return result


@router.get("/build/projects")
async def list_build_projects() -> dict:
    projects = [p.model_dump() for p in store.list_projects()]
    return {"projects": projects, "count": len(projects)}


@router.get("/build/events")
async def list_build_events(project_id: str | None = None, limit: int = 50) -> dict:
    """Observability: real Build Events emitted by the engine (ring buffer)."""
    items = recent_events(project_id=project_id, limit=min(limit, 200))
    return {"events": [e.model_dump() for e in items], "count": len(items)}


@router.post("/build/evaluate")
async def evaluate_build_project(body: dict) -> dict:
    """Re-evaluate an existing BUILD_PROJECT workspace against a request."""
    project_id = str(body.get("project_id") or "")
    message = str(body.get("message") or "")
    record = store.get_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")
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
async def preview_file(project_id: str, file_path: str) -> FileResponse:
    target = resolve_preview_file(project_id, file_path)
    if target is None:
        raise HTTPException(status_code=404, detail="Preview file not found")
    media, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media or "application/octet-stream")
