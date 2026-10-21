"""Workflow engine: plan, gate on approval, execute, checkpoint, review."""
from __future__ import annotations
import asyncio
import time
from app.core.secrets import contains_secret, redact_secrets
from app.models.errors import (
    ToolPermissionError,
    WorkflowInvalidTaskError,
    WorkflowLimitError,
    WorkflowNotFoundError,
    WorkflowSecurityError,
    WorkflowStateError,
)
from app.workflows.audit import WorkflowAuditLog
from app.workflows.checkpoints import CheckpointManager
from app.workflows.executor import WorkflowExecutor
from app.workflows.graph import blocked_by_failure, ready_tasks, validate_graph
from app.workflows.limits import limit_reason
from app.workflows.models import (
    AGENT_LABELS,
    ApprovalView,
    AutonomyLevel,
    RiskLevel,
    Workflow,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowLimits,
    WorkflowState,
    WorkflowStatus,
    WorkflowTask,
    agent_label,
    utcnow,
)
from app.workflows.planner import WorkflowPlanner
from app.workflows.reviewer import WorkflowReviewer
_AGENT_ACTORS = frozenset(AGENT_LABELS) | {"agent", "workflow", "system"}
class WorkflowEngine:
    def __init__(self, registry, knowledge_base=None, model_gateway=None, runner=None, planner=None) -> None:
        self._executor = WorkflowExecutor(
            registry, knowledge_base=knowledge_base, model_gateway=model_gateway, runner=runner
        )
        self._planner = planner or WorkflowPlanner()
        self._checkpoints = CheckpointManager()
        self._audit = WorkflowAuditLog()
        self._reviewer = WorkflowReviewer()
        self._workflows: dict[str, Workflow] = {}
        self._lock = asyncio.Lock()
    def create(
        self,
        goal: str,
        *,
        name: str | None = None,
        description: str | None = None,
        autonomy: AutonomyLevel | str = AutonomyLevel.ASSISTED,
        project_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        limits: WorkflowLimits | None = None,
        tasks: list[WorkflowTask] | None = None,
    ) -> Workflow:
        if not goal or not goal.strip():
            raise WorkflowInvalidTaskError("Workflow goal must not be empty.")
        try:
            level = autonomy if isinstance(autonomy, AutonomyLevel) else AutonomyLevel(str(autonomy))
        except ValueError as exc:
            raise WorkflowInvalidTaskError("Unknown autonomy level.") from exc
        bounds = limits or WorkflowLimits()
        planned = tasks if tasks is not None else self._planner.plan(goal, bounds)
        if len(planned) > bounds.max_tasks:
            raise WorkflowLimitError("maximum tasks")
        validate_graph(planned)
        workflow = Workflow(
            user_id=user_id,
            name=name or _title_from_goal(goal),
            description=description or goal.strip(),
            goal=goal.strip(),
            autonomy=level,
            limits=bounds,
            tasks=planned,
        )
        workflow.context.workflow_goal = workflow.goal
        workflow.context.project_id = project_id
        workflow.context.conversation_id = conversation_id
        workflow.state = WorkflowState(status=WorkflowStatus.PENDING)
        self._emit(workflow, WorkflowEventType.WORKFLOW_CREATED, "Workflow created")
        self._checkpoints.save(workflow, "Planning complete")
        self._audit.record(workflow, status=WorkflowStatus.PENDING.value)
        self._workflows[workflow.id] = workflow
        return workflow
    def list(self, *, user_id: str | None = None) -> list[Workflow]:
        items = list(self._workflows.values())
        if user_id is not None:
            items = [w for w in items if w.user_id == user_id]
        return items
    def get(self, workflow_id: str, *, user_id: str | None = None) -> Workflow:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id)
        if user_id is not None and workflow.user_id != user_id:
            raise WorkflowNotFoundError(workflow_id)
        return workflow
    def delete_user_workflows(self, user_id: str) -> int:
        to_remove = [wid for wid, w in self._workflows.items() if w.user_id == user_id]
        for wid in to_remove:
            del self._workflows[wid]
        return len(to_remove)
    async def start(self, workflow_id: str) -> Workflow:
        workflow = self.get(workflow_id)
        if workflow.status not in (WorkflowStatus.PENDING, WorkflowStatus.PAUSED):
            raise WorkflowStateError(f"Cannot start a workflow in status {workflow.status.value}.")
        resumed = workflow.status == WorkflowStatus.PAUSED
        workflow.state.pause_requested = False
        workflow.state.cancel_requested = False
        workflow.state.status = WorkflowStatus.RUNNING
        if workflow.state.started_at is None:
            workflow.state.started_at = utcnow()
        self._emit(
            workflow,
            WorkflowEventType.WORKFLOW_RESUMED if resumed else WorkflowEventType.WORKFLOW_STARTED,
            "Workflow resumed" if resumed else "Workflow started",
        )
        await self._drive(workflow)
        return workflow
    async def pause(self, workflow_id: str) -> Workflow:
        workflow = self.get(workflow_id)
        if workflow.status not in (WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.PENDING):
            raise WorkflowStateError(f"Cannot pause a workflow in status {workflow.status.value}.")
        workflow.state.pause_requested = True
        if workflow.status != WorkflowStatus.RUNNING:
            workflow.state.status = WorkflowStatus.PAUSED
            workflow.pending_approval = None
            self._emit(workflow, WorkflowEventType.WORKFLOW_PAUSED, "Workflow paused")
        return workflow
    async def resume(self, workflow_id: str) -> Workflow:
        workflow = self.get(workflow_id)
        if workflow.status == WorkflowStatus.FAILED:
            self._recover(workflow)
        if workflow.status not in (WorkflowStatus.PAUSED, WorkflowStatus.RUNNING):
            raise WorkflowStateError(f"Cannot resume a workflow in status {workflow.status.value}.")
        return await self.start(workflow_id)
    async def cancel(self, workflow_id: str) -> Workflow:
        workflow = self.get(workflow_id)
        if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            raise WorkflowStateError(f"Cannot cancel a workflow in status {workflow.status.value}.")
        workflow.state.cancel_requested = True
        workflow.pending_approval = None
        for task in workflow.tasks:
            if task.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL):
                task.status = WorkflowStatus.CANCELLED
        workflow.state.status = WorkflowStatus.CANCELLED
        workflow.error = "cancelled"
        self._emit(workflow, WorkflowEventType.WORKFLOW_CANCELLED, "Workflow cancelled")
        self._audit.record(workflow, status=WorkflowStatus.CANCELLED.value)
        return workflow
    async def approve(self, workflow_id: str, *, actor: str = "user") -> Workflow:
        self._reject_self_approval(actor)
        workflow = self.get(workflow_id)
        if workflow.status != WorkflowStatus.WAITING_APPROVAL or workflow.pending_approval is None:
            raise WorkflowStateError("This workflow is not waiting for approval.")
        task = self._task(workflow, workflow.pending_approval.task_id)
        task.approved = True
        task.status = WorkflowStatus.PENDING
        workflow.pending_approval = None
        workflow.state.status = WorkflowStatus.RUNNING
        self._emit(workflow, WorkflowEventType.APPROVAL_GRANTED, f"Approved {task.name}", task_id=task.id)
        self._audit.record(workflow, status="approval_granted", task_id=task.id, agent=task.agent, approval="granted")
        await self._drive(workflow)
        return workflow
    async def reject(self, workflow_id: str, *, actor: str = "user") -> Workflow:
        self._reject_self_approval(actor)
        workflow = self.get(workflow_id)
        if workflow.status != WorkflowStatus.WAITING_APPROVAL or workflow.pending_approval is None:
            raise WorkflowStateError("This workflow is not waiting for approval.")
        task = self._task(workflow, workflow.pending_approval.task_id)
        task.status = WorkflowStatus.FAILED
        task.error = "approval rejected"
        workflow.pending_approval = None
        self._fail(workflow, "approval rejected", task)
        self._emit(workflow, WorkflowEventType.APPROVAL_REJECTED, f"Rejected {task.name}", task_id=task.id)
        self._audit.record(
            workflow, status="approval_rejected", task_id=task.id, agent=task.agent, approval="rejected", error=task.error
        )
        return workflow
    async def _drive(self, workflow: Workflow) -> None:
        started = time.perf_counter()
        while True:
            workflow.state.loop_iterations += 1
            if workflow.state.loop_iterations > workflow.limits.max_tasks * (workflow.limits.max_retries + 2) + 4:
                self._fail(workflow, "loop protection")
                return
            workflow.state.elapsed_seconds += time.perf_counter() - started
            started = time.perf_counter()
            if workflow.state.cancel_requested:
                await self.cancel(workflow.id)
                return
            if workflow.state.pause_requested:
                workflow.state.status = WorkflowStatus.PAUSED
                self._emit(workflow, WorkflowEventType.WORKFLOW_PAUSED, "Workflow paused")
                return
            reason = limit_reason(workflow)
            if reason:
                self._fail(workflow, f"limit reached: {reason}")
                return
            self._mark_blocked(workflow)
            if self._finish_if_done(workflow):
                return
            ready = ready_tasks(workflow.tasks)
            if not ready:
                if any(task.status == WorkflowStatus.FAILED for task in workflow.tasks):
                    self._fail(workflow, workflow.error or "dependency failure")
                return
            waiting = [task for task in ready if self._needs_approval(workflow, task)]
            if waiting:
                self._request_approval(workflow, waiting[0])
                return
            batch = self._parallel_batch(workflow, ready)
            await asyncio.gather(*(self._run_task(workflow, task) for task in batch))
    def _parallel_batch(self, workflow: Workflow, ready: list[WorkflowTask]) -> list[WorkflowTask]:
        cap = max(1, workflow.limits.max_parallel_tasks)
        safe = [task for task in ready if task.risk == RiskLevel.SAFE]
        if len(safe) >= 2:
            return safe[:cap]
        return ready[:1]
    def _needs_approval(self, workflow: Workflow, task: WorkflowTask) -> bool:
        if task.approved:
            return False
        if workflow.autonomy == AutonomyLevel.MANUAL:
            return True
        return task.risk == RiskLevel.DANGEROUS
    def _request_approval(self, workflow: Workflow, task: WorkflowTask) -> None:
        task.status = WorkflowStatus.WAITING_APPROVAL
        workflow.state.status = WorkflowStatus.WAITING_APPROVAL
        workflow.pending_approval = ApprovalView(
            task_id=task.id,
            agent=agent_label(task.agent),
            action=task.description,
            resources=list(task.resources),
            consequences=task.consequences or "This action needs confirmation before it runs.",
        )
        self._emit(workflow, WorkflowEventType.APPROVAL_REQUIRED, task.description, task_id=task.id)
        self._audit.record(workflow, status="approval_required", task_id=task.id, agent=task.agent, tool=task.tool)
    async def _run_task(self, workflow: Workflow, task: WorkflowTask) -> None:
        task.status = WorkflowStatus.RUNNING
        self._emit(workflow, WorkflowEventType.TASK_STARTED, task.name, task_id=task.id)
        self._audit.record(workflow, status=WorkflowStatus.RUNNING.value, task_id=task.id, agent=task.agent, tool=task.tool)
        cancel = asyncio.Event()
        attempts = workflow.limits.max_retries + 1
        while True:
            try:
                outcome = await self._executor.run(workflow, task, cancel)
            except ToolPermissionError as exc:
                task.error = "permission denied"
                task.status = WorkflowStatus.FAILED
                self._audit.record(
                    workflow, status="permission_denied", task_id=task.id, agent=task.agent, tool=task.tool, error=exc.message
                )
                self._emit(workflow, WorkflowEventType.TASK_FAILED, task.error, task_id=task.id)
                return
            except (TimeoutError, asyncio.TimeoutError, RuntimeError, OSError) as exc:
                task.retry_count += 1
                message = "timeout" if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) else str(exc)
                if task.retry_count >= attempts:
                    task.error = message
                    task.status = WorkflowStatus.FAILED
                    self._audit.record(
                        workflow, status=WorkflowStatus.FAILED.value, task_id=task.id, agent=task.agent, tool=task.tool, error=message
                    )
                    self._emit(workflow, WorkflowEventType.TASK_FAILED, message, task_id=task.id)
                    return
                continue
            if contains_secret(outcome.output):
                task.output = redact_secrets(outcome.output)
                task.error = "secret blocked"
                task.status = WorkflowStatus.FAILED
                self._audit.record(
                    workflow, status=WorkflowStatus.FAILED.value, task_id=task.id, agent=task.agent, error=task.error
                )
                self._emit(workflow, WorkflowEventType.TASK_FAILED, task.error, task_id=task.id)
                return
            task.output = outcome.output
            task.status = WorkflowStatus.COMPLETED
            task.error = None
            workflow.state.tool_calls += outcome.tool_calls
            workflow.state.tokens_used += outcome.tokens
            workflow.state.cost_used += outcome.cost
            for source in outcome.sources:
                if source not in workflow.sources:
                    workflow.sources.append(source)
            self._emit(workflow, WorkflowEventType.TASK_COMPLETED, task.name, task_id=task.id)
            self._audit.record(
                workflow, status=WorkflowStatus.COMPLETED.value, task_id=task.id, agent=task.agent, tool=outcome.tool or task.tool
            )
            if task.checkpoint_name:
                self._checkpoints.save(workflow, task.checkpoint_name)
            return
    def _mark_blocked(self, workflow: Workflow) -> None:
        for task in blocked_by_failure(workflow.tasks):
            task.status = WorkflowStatus.FAILED
            task.error = "dependency failure"
            self._emit(workflow, WorkflowEventType.TASK_FAILED, task.error, task_id=task.id)
    def _finish_if_done(self, workflow: Workflow) -> bool:
        if any(task.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL) for task in workflow.tasks):
            return False
        if any(task.status == WorkflowStatus.FAILED for task in workflow.tasks):
            self._fail(workflow, workflow.error or "task failed")
            return True
        if not all(task.status == WorkflowStatus.COMPLETED for task in workflow.tasks):
            return False
        draft = next((task.output for task in workflow.tasks if task.name == "Draft" and task.output), None)
        workflow.final_result = draft or next((task.output for task in reversed(workflow.tasks) if task.output), "")
        if workflow.sources:
            workflow.final_result = (workflow.final_result or "") + "\n\nSources:\n" + "\n".join(f"- {item}" for item in workflow.sources)
        ok, detail = self._reviewer.review(workflow)
        if not ok:
            self._fail(workflow, detail)
            return True
        workflow.final_result = redact_secrets(workflow.final_result or detail)
        workflow.error = None
        workflow.state.status = WorkflowStatus.COMPLETED
        self._emit(workflow, WorkflowEventType.WORKFLOW_COMPLETED, "Workflow completed")
        self._audit.record(workflow, status=WorkflowStatus.COMPLETED.value)
        return True
    def _fail(self, workflow: Workflow, reason: str, task: WorkflowTask | None = None) -> None:
        workflow.error = reason
        workflow.state.status = WorkflowStatus.FAILED
        workflow.final_result = None
        self._emit(workflow, WorkflowEventType.WORKFLOW_FAILED, reason, task_id=task.id if task else None)
        self._audit.record(workflow, status=WorkflowStatus.FAILED.value, task_id=task.id if task else None, error=reason)
    def _recover(self, workflow: Workflow) -> None:
        checkpoint = self._checkpoints.last(workflow)
        if checkpoint is None or workflow.state.recovery_count >= 1:
            raise WorkflowStateError("No safe checkpoint to resume from.")
        done = set(checkpoint.completed_task_ids)
        for task in workflow.tasks:
            if task.id in done:
                continue
            if task.status == WorkflowStatus.FAILED:
                task.status = WorkflowStatus.PENDING
                task.error = None
                task.retry_count = 0
        workflow.error = None
        workflow.state.recovery_count += 1
        workflow.state.status = WorkflowStatus.PAUSED
        workflow.state.pause_requested = False
    def _emit(self, workflow: Workflow, event_type: WorkflowEventType, message: str, task_id: str | None = None) -> None:
        workflow.events.append(
            WorkflowEvent(type=event_type, workflow_id=workflow.id, task_id=task_id, message=redact_secrets(message))
        )
    def _task(self, workflow: Workflow, task_id: str) -> WorkflowTask:
        for task in workflow.tasks:
            if task.id == task_id:
                return task
        raise WorkflowNotFoundError(task_id)
    @staticmethod
    def _reject_self_approval(actor: str) -> None:
        if actor.strip().lower() in _AGENT_ACTORS:
            raise WorkflowSecurityError("An agent cannot approve its own action.")
def _title_from_goal(goal: str) -> str:
    text = " ".join(goal.split())
    return text[:48] + ("…" if len(text) > 48 else "")
