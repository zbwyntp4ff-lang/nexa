"""Legacy orchestrator workflow API (Part 7).

Stateless: no durable task store. Requires auth when ``TOKENS_ENFORCE=true``.
Honours ``WORKFLOWS_ENABLED`` the same as ``/api/v1/workflows``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_orchestrator, get_settings
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.config.settings import Settings
from app.models.errors import FeatureDisabledError
from app.orchestrator.models import (
    ApprovalRequest,
    SubTask,
    WorkflowStatus,
    WorkflowTask,
)

router = APIRouter(prefix="/api/v1", tags=["workflow"])


class WorkflowRunRequest(BaseModel):
    task: str = Field(..., description="The complex user task")
    metadata: dict = Field(default_factory=dict)
    attachment_ids: list[str] = Field(
        default_factory=list,
        description="Attachment ids whose document context research/coding/planning agents may use.",
    )


class ApprovalResponse(BaseModel):
    subtask_id: str
    approved: bool


class WorkflowResponse(BaseModel):
    task_id: str
    status: WorkflowStatus
    subtasks: list[SubTask]
    final_answer: str | None = None
    elapsed_ms: float = 0.0
    approval_required: bool = False
    approval_description: str | None = None
    provider: str | None = None
    model: str | None = None


def _require_workflows(settings: Settings) -> None:
    if not settings.workflows_enabled:
        raise FeatureDisabledError(
            "Workflows are disabled on this server "
            "(no durable task store; see WORKFLOWS_ENABLED)."
        )


@router.post("/workflow", response_model=WorkflowResponse)
async def run_workflow(
    request: WorkflowRunRequest,
    orchestrator=Depends(get_orchestrator),
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    task = WorkflowTask(
        description=request.task,
        metadata=request.metadata,
        attachment_ids=request.attachment_ids,
    )
    result = await orchestrator.run(task)
    return WorkflowResponse(**result.model_dump())


@router.post("/workflow/{task_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(
    task_id: str,
    orchestrator=Depends(get_orchestrator),
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    raise HTTPException(
        status_code=501,
        detail="Workflow cancellation is not supported in the stateless API yet.",
    )


@router.get("/workflow/{task_id}", response_model=WorkflowResponse)
async def get_workflow(
    task_id: str,
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    raise HTTPException(status_code=404, detail="Workflow persistence is not implemented yet.")


@router.get("/workflow/{task_id}/approvals", response_model=list[ApprovalRequest])
async def get_pending_approvals(
    task_id: str,
    orchestrator=Depends(get_orchestrator),
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
    settings: Settings = Depends(get_settings),
) -> list[ApprovalRequest]:
    _require_workflows(settings)
    return orchestrator.get_pending_approvals()


@router.post("/workflow/{task_id}/approve", response_model=WorkflowResponse)
async def resolve_approval(
    task_id: str,
    request: ApprovalResponse,
    orchestrator=Depends(get_orchestrator),
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    _require_workflows(settings)
    orchestrator.resolve_approval(request.subtask_id, request.approved)
    raise HTTPException(status_code=200, detail="Approval resolved.")
