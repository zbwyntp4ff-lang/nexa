"""Autonomous workflow API (Part 10) — per-user ownership enforced.

Public durable launch should set ``WORKFLOWS_ENABLED=false`` until a durable
store exists; otherwise state is lost on process restart.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_settings, get_workflow_engine
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.config.settings import Settings
from app.models.errors import FeatureDisabledError
from app.workflows.models import public_view

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])
_Auth = Annotated[UserRecord | None, Depends(require_user_when_enforced)]


class CreateWorkflowRequest(BaseModel):
    goal: str
    name: str | None = None
    description: str | None = None
    autonomy: str = "assisted"
    project_id: str | None = None
    conversation_id: str | None = None


class ActorRequest(BaseModel):
    actor: str = "user"


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    goal: str
    autonomy: str
    status: str
    progress: float
    current_task: str | None = None
    error: str | None = None
    final_result: str | None = None
    sources: list[str] = Field(default_factory=list)
    pending_approval: dict | None = None
    checkpoints: list[dict] = Field(default_factory=list)
    tasks: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    limits: dict = Field(default_factory=dict)
    created_at: datetime


def _uid(user: UserRecord | None) -> str | None:
    return user.id if user is not None else None


def _view(workflow) -> WorkflowResponse:
    return WorkflowResponse(**public_view(workflow))


def _require_workflows(settings: Settings) -> None:
    if not settings.workflows_enabled:
        raise FeatureDisabledError(
            "Autonomous workflows are disabled on this server "
            "(in-memory only; set WORKFLOWS_ENABLED=true only if restart loss is acceptable)."
        )


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    body: CreateWorkflowRequest,
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    workflow = engine.create(
        body.goal,
        name=body.name,
        description=body.description,
        autonomy=body.autonomy,
        project_id=body.project_id,
        conversation_id=body.conversation_id,
        user_id=_uid(user),
    )
    return _view(workflow)


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> list[WorkflowResponse]:
    _require_workflows(settings)
    return [_view(item) for item in engine.list(user_id=_uid(user))]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    return _view(engine.get(workflow_id, user_id=_uid(user)))


@router.post("/{workflow_id}/start", response_model=WorkflowResponse)
async def start_workflow(
    workflow_id: str,
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    engine.get(workflow_id, user_id=_uid(user))
    return _view(await engine.start(workflow_id))


@router.post("/{workflow_id}/pause", response_model=WorkflowResponse)
async def pause_workflow(
    workflow_id: str,
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    engine.get(workflow_id, user_id=_uid(user))
    return _view(await engine.pause(workflow_id))


@router.post("/{workflow_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(
    workflow_id: str,
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    engine.get(workflow_id, user_id=_uid(user))
    return _view(await engine.resume(workflow_id))


@router.post("/{workflow_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(
    workflow_id: str,
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    engine.get(workflow_id, user_id=_uid(user))
    return _view(await engine.cancel(workflow_id))


@router.post("/{workflow_id}/approve", response_model=WorkflowResponse)
async def approve_workflow(
    workflow_id: str,
    body: ActorRequest = Body(default_factory=ActorRequest),
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    engine.get(workflow_id, user_id=_uid(user))
    return _view(await engine.approve(workflow_id, actor=body.actor))


@router.post("/{workflow_id}/reject", response_model=WorkflowResponse)
async def reject_workflow(
    workflow_id: str,
    body: ActorRequest = Body(default_factory=ActorRequest),
    engine=Depends(get_workflow_engine),
    user: _Auth = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    engine.get(workflow_id, user_id=_uid(user))
    return _view(await engine.reject(workflow_id, actor=body.actor))
