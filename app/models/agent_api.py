"""Request/response models for the ``POST /api/v1/agent`` endpoint."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from app.agent.models import AgentStatus, AgentStepType
class AgentRunRequest(BaseModel):
    task: str = Field(..., description="Natural-language description of what the agent should do")
    dry_run: bool = Field(default=False, description="Simulate the plan without real side effects")
    attachment_ids: list[str] = Field(
        default_factory=list,
        description="Attachment ids (from POST /api/v1/attachments) whose document context this agent may use.",
    )
    disabled_tools: list[str] = Field(
        default_factory=list,
        description="Tool names the user has turned off in Settings -> Plugins; the agent will refuse to call them.",
    )
class AgentStepResponse(BaseModel):
    index: int
    step_type: AgentStepType
    tool_name: str | None
    tool_input: dict
    output: object
    success: bool
    error: str | None
    dry_run: bool
    timestamp: datetime
class AgentRunResponse(BaseModel):
    task_id: str
    status: AgentStatus
    success: bool
    final_answer: str | None
    steps: list[AgentStepResponse]
    elapsed_ms: float
    dry_run: bool
    provider: str | None = None
    model: str | None = None
    display_name: str | None = None
