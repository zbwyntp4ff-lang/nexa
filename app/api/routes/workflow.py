"""Workflow API endpoints (Part 7): run, query, cancel workflows."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import get_orchestrator
from app.orchestrator.models import (
    ApprovalRequest,
    SubTask,
    WorkflowResult,
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
@router.post("/workflow", response_model=WorkflowResponse)
async def run_workflow(
    request: WorkflowRunRequest,
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    task = WorkflowTask(description=request.task, metadata=request.metadata, attachment_ids=request.attachment_ids)
    result = await orchestrator.run(task)
    return WorkflowResponse(**result.model_dump())
@router.post("/workflow/{task_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(
    task_id: str,
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    # The rule-based orchestrator runs synchronously; cancellation is cooperative.
    # For the API, we return a FAILED status since there's no persistent store.
    raise HTTPException(status_code=501, detail="Workflow cancellation is not supported in the stateless API yet.")
@router.get("/workflow/{task_id}", response_model=WorkflowResponse)
async def get_workflow(task_id: str) -> WorkflowResponse:
    raise HTTPException(status_code=404, detail="Workflow persistence is not implemented yet.")
@router.get("/workflow/{task_id}/approvals", response_model=list[ApprovalRequest])
async def get_pending_approvals(
    task_id: str,
    orchestrator=Depends(get_orchestrator),
) -> list[ApprovalRequest]:
    return orchestrator.get_pending_approvals()
@router.post("/workflow/{task_id}/approve", response_model=WorkflowResponse)
async def resolve_approval(
    task_id: str,
    request: ApprovalResponse,
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    orchestrator.resolve_approval(request.subtask_id, request.approved)
    raise HTTPException(status_code=200, detail="Approval resolved.")
