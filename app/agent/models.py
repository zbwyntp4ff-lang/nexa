"""Data models for the NEXA agent loop.
Architecture (see README): User -> Agent -> Planner -> (Model) -> Tool
Selector -> Tool -> Observation -> Verifier -> loop or Final Answer.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
def _new_id() -> str:
    return uuid.uuid4().hex
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
class AgentTask(BaseModel):
    """A unit of work handed to the agent."""
    id: str = Field(default_factory=_new_id)
    description: str
    dry_run: bool = False
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    #: Optional extra context (e.g. a bounded document excerpt) to combine
    #: with the task when the model is asked for a free-form answer. The
    #: agent stays unaware of where this text came from (Part 8).
    context: str | None = None
    #: Tool names the user has turned off in Settings -> Plugins. The agent
    #: records a clear error step (not a silent skip) if the planner picks
    #: one of these, instead of actually calling it.
    disabled_tools: frozenset[str] = Field(default_factory=frozenset)
class AgentStepType(str, Enum):
    TOOL_CALL = "tool_call"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
class AgentStep(BaseModel):
    """A single step taken by the agent during a run."""
    index: int
    step_type: AgentStepType
    tool_name: str | None = None
    tool_input: dict = Field(default_factory=dict)
    output: Any = None
    success: bool
    error: str | None = None
    dry_run: bool = False
    timestamp: datetime = Field(default_factory=_utcnow)
class AgentStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    ERROR_LIMIT_EXCEEDED = "error_limit_exceeded"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
class AgentState(BaseModel):
    """Mutable state threaded through a single agent run."""
    task: AgentTask
    steps: list[AgentStep] = Field(default_factory=list)
    error_count: int = 0
    status: AgentStatus = AgentStatus.RUNNING
    model_config = {"arbitrary_types_allowed": True}
    def last_successful_output(self, tool_name: str) -> Any | None:
        for step in reversed(self.steps):
            if step.tool_name == tool_name and step.success:
                return step.output
        return None
    def has_succeeded(self, tool_name: str) -> bool:
        return any(s.tool_name == tool_name and s.success for s in self.steps)
class PlannedActionType(str, Enum):
    TOOL_CALL = "tool_call"
    FINAL_ANSWER = "final_answer"
class PlannedAction(BaseModel):
    """A single decision produced by the :class:`Planner` for one loop iteration."""
    type: PlannedActionType
    tool_name: str | None = None
    tool_input: dict = Field(default_factory=dict)
    final_answer: str | None = None
    rationale: str = ""
class AgentResult(BaseModel):
    """The final outcome of an agent run."""
    task_id: str
    status: AgentStatus
    success: bool
    final_answer: str | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    elapsed_ms: float = 0.0
    dry_run: bool = False
    provider: str | None = None
    model: str | None = None
    display_name: str | None = None
    #: Phase 3 project execution status (planning/running/verifying/...).
    project_status: str | None = None
    project_id: str | None = None
    project_manifest: dict | None = None
    partial_success: bool = False
