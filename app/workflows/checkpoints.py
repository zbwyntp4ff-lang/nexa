"""Checkpoints taken after planning and after named stages."""
from __future__ import annotations
from app.workflows.models import Checkpoint, Workflow, WorkflowEvent, WorkflowEventType, WorkflowStatus, utcnow
class CheckpointManager:
    def save(self, workflow: Workflow, name: str) -> Checkpoint:
        completed = [task.id for task in workflow.tasks if task.status == WorkflowStatus.COMPLETED]
        checkpoint = Checkpoint(name=name, completed_task_ids=completed)
        workflow.checkpoints.append(checkpoint)
        workflow.events.append(
            WorkflowEvent(
                type=WorkflowEventType.CHECKPOINT_CREATED,
                workflow_id=workflow.id,
                message=name,
                timestamp=utcnow(),
            )
        )
        return checkpoint
    def last(self, workflow: Workflow) -> Checkpoint | None:
        if not workflow.checkpoints:
            return None
        return workflow.checkpoints[-1]
