"""Autonomous workflow API (Part 10).
These routes are separate from the Part 7 ``/api/v1/workflow`` endpoint.
"""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from app.api.deps import get_workflow_engine
from app.workflows.models import public_view
router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])
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
def _view(workflow) -> WorkflowResponse:
    return WorkflowResponse(**public_view(workflow))
@router.post("", response_model=WorkflowResponse)
async def create_workflow(body: CreateWorkflowRequest, engine=Depends(get_workflow_engine)) -> WorkflowResponse:
    workflow = engine.create(
        body.goal,
        name=body.name,
        description=body.description,
        autonomy=body.autonomy,
        project_id=body.project_id,
        conversation_id=body.conversation_id,
    )
    return _view(workflow)
@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(engine=Depends(get_workflow_engine)) -> list[WorkflowResponse]:
    return [_view(item) for item in engine.list()]
@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, engine=Depends(get_workflow_engine)) -> WorkflowResponse:
    return _view(engine.get(workflow_id))
@router.post("/{workflow_id}/start", response_model=WorkflowResponse)
async def start_workflow(workflow_id: str, engine=Depends(get_workflow_engine)) -> WorkflowResponse:
    return _view(await engine.start(workflow_id))
@router.post("/{workflow_id}/pause", response_model=WorkflowResponse)
async def pause_workflow(workflow_id: str, engine=Depends(get_workflow_engine)) -> WorkflowResponse:
    return _view(await engine.pause(workflow_id))
@router.post("/{workflow_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(workflow_id: str, engine=Depends(get_workflow_engine)) -> WorkflowResponse:
    return _view(await engine.resume(workflow_id))
@router.post("/{workflow_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(workflow_id: str, engine=Depends(get_workflow_engine)) -> WorkflowResponse:
    return _view(await engine.cancel(workflow_id))
@router.post("/{workflow_id}/approve", response_model=WorkflowResponse)
async def approve_workflow(
    workflow_id: str,
    body: ActorRequest = Body(default_factory=ActorRequest),
    engine=Depends(get_workflow_engine),
) -> WorkflowResponse:
    return _view(await engine.approve(workflow_id, actor=body.actor))
@router.post("/{workflow_id}/reject", response_model=WorkflowResponse)
async def reject_workflow(
    workflow_id: str,
    body: ActorRequest = Body(default_factory=ActorRequest),
    engine=Depends(get_workflow_engine),
) -> WorkflowResponse:
    actor = body.actor
    return _view(await engine.reject(workflow_id, actor=actor))
