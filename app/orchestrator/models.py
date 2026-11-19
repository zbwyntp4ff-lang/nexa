"""Workflow state machine for the Multi-Agent Orchestrator (Part 7).
A workflow is a user-level task that the Orchestrator decomposes into
subtasks, assigns to specialized agents, tracks dependencies, and
merges results. States:
    PENDING -> RUNNING -> WAITING_APPROVAL -> COMPLETED/FAILED/CANCELLED
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
class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
class SubTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
class SubTask(BaseModel):
    """A single subtask within a workflow."""
    id: str = Field(default_factory=_new_id)
    agent_type: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    status: SubTaskStatus = SubTaskStatus.PENDING
    result: str | None = None
    provider: str | None = None
    model: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
class WorkflowTask(BaseModel):
    """The top-level user task handed to the Orchestrator."""
    id: str = Field(default_factory=_new_id)
    description: str
    metadata: dict = Field(default_factory=dict)
    attachment_ids: list[str] = Field(default_factory=list)
    user_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
class WorkflowResult(BaseModel):
    """The final outcome of a workflow run."""
    task_id: str
    status: WorkflowStatus
    subtasks: list[SubTask]
    final_answer: str | None = None
    elapsed_ms: float = 0.0
    approval_required: bool = False
    approval_description: str | None = None
    provider: str | None = None
    model: str | None = None
class ApprovalRequest(BaseModel):
    """Describes a potentially dangerous action that needs user approval."""
    subtask_id: str
    agent_type: str
    action_description: str
    tool_name: str
    tool_input: dict
