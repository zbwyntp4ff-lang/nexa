"""Agent endpoint - runs the Part 2 Agent loop (Planner -> Tool Selector ->
Executor -> Verifier) for a single task and returns its full result.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.agent.agent import Agent
from app.agent.models import AgentTask
from app.api.deps import get_agent
from app.attachments.manager import AttachmentManager, get_attachment_manager
from app.models.agent_api import AgentRunRequest, AgentRunResponse
router = APIRouter(prefix="/api/v1", tags=["agent"])
@router.post("/agent", response_model=AgentRunResponse)
async def run_agent(
    request: AgentRunRequest,
    agent: Agent = Depends(get_agent),
    attachments: AttachmentManager = Depends(get_attachment_manager),
) -> AgentRunResponse:
    context = (
        attachments.document_context(request.attachment_ids, query=request.task)
        if request.attachment_ids
        else None
    )
    task = AgentTask(
        description=request.task,
        dry_run=request.dry_run,
        context=context or None,
        disabled_tools=frozenset(request.disabled_tools),
    )
    result = await agent.run(task)
    return AgentRunResponse(**result.model_dump())
