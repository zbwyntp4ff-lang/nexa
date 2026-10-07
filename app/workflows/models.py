"""State, tasks, events, and limits for Autonomous Workflows (Part 10)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
def new_id() -> str:
    return uuid.uuid4().hex
def utcnow() -> datetime:
    return datetime.now(timezone.utc)
class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
class AutonomyLevel(str, Enum):
    MANUAL = "manual"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"
class RiskLevel(str, Enum):
    SAFE = "safe"
    DANGEROUS = "dangerous"
class WorkflowEventType(str, Enum):
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_STARTED = "workflow_started"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    CHECKPOINT_CREATED = "checkpoint_created"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_FAILED = "workflow_failed"
class WorkflowLimits(BaseModel):
    """Hard caps. Hitting one stops the workflow; it is never marked completed."""
    max_tasks: int = 8
    max_execution_seconds: float = 300.0
    max_retries: int = 2
    max_parallel_tasks: int = 2
    max_tool_calls: int = 20
    token_budget: int = 8000
    cost_budget: float | None = None
class WorkflowTask(BaseModel):
    """One node in the task graph."""
    id: str = Field(default_factory=new_id)
    name: str
    description: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    agent: str
    input: str = ""
    output: str | None = None
    retry_count: int = 0
    timeout: float = 30.0
    risk: RiskLevel = RiskLevel.SAFE
    tool: str | None = None
    resources: list[str] = Field(default_factory=list)
    consequences: str = ""
    approved: bool = False
    error: str | None = None
    checkpoint_name: str | None = None
    required: bool = True
class WorkflowEvent(BaseModel):
    type: WorkflowEventType
    workflow_id: str
    task_id: str | None = None
    message: str = ""
    timestamp: datetime = Field(default_factory=utcnow)
class Checkpoint(BaseModel):
    name: str
    completed_task_ids: list[str]
    created_at: datetime = Field(default_factory=utcnow)
class ApprovalView(BaseModel):
    task_id: str
    agent: str
    action: str
    resources: list[str] = Field(default_factory=list)
    consequences: str = ""
class AuditRecord(BaseModel):
    workflow_id: str
    task_id: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    agent: str | None = None
    tool: str | None = None
    status: str
    approval: str | None = None
    error: str | None = None
class ContextScope(BaseModel):
    """Isolated context layers. A task never receives the conversation history."""
    global_notes: str = ""
    project_id: str | None = None
    conversation_id: str | None = None
    workflow_goal: str = ""
class WorkflowState(BaseModel):
    """Mutable runtime counters kept separate from the task graph."""
    status: WorkflowStatus = WorkflowStatus.PENDING
    pause_requested: bool = False
    cancel_requested: bool = False
    tool_calls: int = 0
    tokens_used: int = 0
    cost_used: float = 0.0
    started_at: datetime | None = None
    elapsed_seconds: float = 0.0
    recovery_count: int = 0
    loop_iterations: int = 0
class Workflow(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    description: str
    goal: str
    autonomy: AutonomyLevel = AutonomyLevel.ASSISTED
    state: WorkflowState = Field(default_factory=WorkflowState)
    tasks: list[WorkflowTask] = Field(default_factory=list)
    limits: WorkflowLimits = Field(default_factory=WorkflowLimits)
    context: ContextScope = Field(default_factory=ContextScope)
    events: list[WorkflowEvent] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    audit: list[AuditRecord] = Field(default_factory=list)
    pending_approval: ApprovalView | None = None
    final_result: str | None = None
    sources: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    @property
    def status(self) -> WorkflowStatus:
        return self.state.status
    def progress(self) -> float:
        if not self.tasks:
            return 0.0
        done = sum(1 for task in self.tasks if task.status == WorkflowStatus.COMPLETED)
        return done / len(self.tasks)
    def current_task_name(self) -> str | None:
        for task in self.tasks:
            if task.status in (WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL):
                return task.name
        for task in self.tasks:
            if task.status == WorkflowStatus.PENDING:
                return task.name
        return None
class TaskOutcome(BaseModel):
    """What an executor returns for one task attempt."""
    output: str
    tool: str | None = None
    tool_calls: int = 0
    tokens: int = 0
    cost: float = 0.0
    sources: list[str] = Field(default_factory=list)
    model_config = {"arbitrary_types_allowed": True}
# Agents that already exist. Workflows must not invent new ones.
KNOWN_AGENTS = frozenset({"research", "coding", "planning", "desktop", "review"})
# Filesystem-writing agents. Every autonomy mode stops for these.
DANGEROUS_AGENTS = frozenset({"desktop", "coding"})
AGENT_LABELS = {
    "research": "Research Agent",
    "coding": "Coding Agent",
    "planning": "Planning Agent",
    "desktop": "Desktop Agent",
    "review": "Review Agent",
}
def agent_label(agent: str) -> str:
    return AGENT_LABELS.get(agent, agent)
def public_view(workflow: Workflow) -> dict[str, Any]:
    """API shape. Audit and outputs are already redacted before they are stored."""
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "goal": workflow.goal,
        "autonomy": workflow.autonomy.value,
        "status": workflow.status.value,
        "progress": workflow.progress(),
        "current_task": workflow.current_task_name(),
        "error": workflow.error,
        "final_result": workflow.final_result,
        "sources": list(workflow.sources),
        "pending_approval": workflow.pending_approval.model_dump() if workflow.pending_approval else None,
        "checkpoints": [item.model_dump() for item in workflow.checkpoints],
        "tasks": [task.model_dump() for task in workflow.tasks],
        "events": [event.model_dump() for event in workflow.events],
        "limits": workflow.limits.model_dump(),
        "created_at": workflow.created_at,
    }
