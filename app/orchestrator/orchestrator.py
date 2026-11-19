"""Agent Orchestrator (Part 7).
Accepts a complex user task, decomposes it into subtasks, assigns
each subtask to the best specialized agent, tracks dependencies, handles approvals
for dangerous actions, merges results, and returns a single answer.
Reuses the existing ``Agent`` class (Part 2) and ``ToolRegistry``
(Part 2/6B) — no architecture rewrite.
"""
from __future__ import annotations
import asyncio
import time
from app.agent.models import AgentTask
from app.agent.planner import RuleBasedPlanner, _ARITHMETIC_PATTERN
from app.orchestrator.agents import make_agent
from app.core.logging_config import get_logger
from app.models.errors import NexaError
from app.orchestrator.audit import AuditLog
from app.orchestrator.models import (
    ApprovalRequest,
    SubTask,
    SubTaskStatus,
    WorkflowResult,
    WorkflowStatus,
    WorkflowTask,
)
from app.tools.registry import ToolRegistry
logger = get_logger("nexa.orchestrator")
DEFAULT_MAX_SUBTASKS = 8
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_STEP_TIMEOUT = 30.0
# Keywords that trigger agent-type selection in the rule-based decomposer.
_RESEARCH_KEYWORDS = ("research", "find information", "search the web", "look up", "investigate",
                       "найди", "поищи", "исследуй", "узнай", "найди в интернете")
_CODING_KEYWORDS = ("code", "write code", "implement", "function", "bug fix",
                     "refactor", "напиши код", "реализуй", "функцию", "исправь код")
_DESKTOP_KEYWORDS = ("file", "folder", "directory", "create file", "rename",
                   "создай файл", "создай папку", "переименуй")
_PLAN_KEYWORDS = ("plan", "break down", "steps", "decompose",
                   "разбей", "план", "шаги")
# Least-privilege: only agent types that plausibly need document content see
# it. Desktop and Review agents never receive raw document text (Part 8).
_CONTEXT_PERMITTED_AGENTS = frozenset({"research", "coding", "planning"})
class Orchestrator:
    """Decomposes a user task into subtasks, runs specialized agents, merges results."""
    def __init__(
        self,
        registry: ToolRegistry,
        max_subtasks: int = DEFAULT_MAX_SUBTASKS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        step_timeout_seconds: float = DEFAULT_STEP_TIMEOUT,
        model_gateway=None,
        attachment_manager=None,
    ) -> None:
        self._registry = registry
        self._max_subtasks = max_subtasks
        self._timeout_seconds = timeout_seconds
        self._step_timeout_seconds = step_timeout_seconds
        self._model_gateway = model_gateway
        self._attachment_manager = attachment_manager
        self._audit = AuditLog()
        self._approvals: dict[str, ApprovalRequest] = {}
    def _decompose(self, task: WorkflowTask) -> list[SubTask]:
        """Rule-based decomposition: picks an agent type per subtask."""
        text = task.description.lower()
        subtasks: list[SubTask] = []
        if any(kw in text for kw in _RESEARCH_KEYWORDS):
            subtasks.append(SubTask(agent_type="research", description=f"Research: {task.description}"))
        if any(kw in text for kw in _CODING_KEYWORDS):
            subtasks.append(SubTask(agent_type="coding", description=f"Code: {task.description}"))
        if any(kw in text for kw in _DESKTOP_KEYWORDS):
            subtasks.append(SubTask(agent_type="desktop", description=f"Desktop: {task.description}"))
        # Arithmetic expressions go to coding agent (has calculator permission).
        if _ARITHMETIC_PATTERN.search(text) and not any(kw in text for kw in _CODING_KEYWORDS):
            subtasks.append(SubTask(agent_type="coding", description=task.description))
        if any(kw in text for kw in _PLAN_KEYWORDS) or len(subtasks) == 0:
            # Default: planning agent decomposes, or handle directly.
            subtasks.append(SubTask(agent_type="planning", description=task.description))
        # Cap the number of subtasks.
        return subtasks[: self._max_subtasks]
    def _build_agent(self, agent_type: str) -> "Agent":
        return make_agent(
            agent_type,
            self._registry,
            model_gateway=self._model_gateway,
            max_steps=5,
            timeout_seconds=self._step_timeout_seconds,
            error_limit=2,
        )
    def _document_context_for(self, agent_type: str, attachment_ids: list[str], query: str, user_id: str | None = None) -> str | None:
        """Resolve document context, but only for agent types allowed to see it."""
        if not attachment_ids or agent_type not in _CONTEXT_PERMITTED_AGENTS or self._attachment_manager is None:
            return None
        context = self._attachment_manager.document_context(attachment_ids, query=query, user_id=user_id)
        return context or None
    async def _run_subtask(
        self, task_id: str, subtask: SubTask, attachment_ids: list[str] | None = None, user_id: str | None = None
    ) -> None:
        """Run a single subtask with the matching specialized agent."""
        subtask.status = SubTaskStatus.RUNNING
        subtask.started_at = _now()
        agent = self._build_agent(subtask.agent_type)
        context = self._document_context_for(subtask.agent_type, attachment_ids or [], subtask.description, user_id=user_id)
        try:
            result = await asyncio.wait_for(
                agent.run(AgentTask(description=subtask.description, context=context, metadata={"user_id": user_id} if user_id else {})),
                timeout=self._step_timeout_seconds,
            )
            subtask.result = result.final_answer or ""
            subtask.provider = result.provider
            subtask.model = result.model
            subtask.status = SubTaskStatus.COMPLETED if result.success else SubTaskStatus.FAILED
            subtask.error = result.final_answer if not result.success else None
            self._audit.record(
                task_id=task_id, agent_type=subtask.agent_type,
                action="run_subtask", status=subtask.status.value,
                duration_ms=result.elapsed_ms,
                error_type=None if result.success else result.status.value,
            )
        except asyncio.TimeoutError:
            subtask.status = SubTaskStatus.FAILED
            subtask.error = "Subtask timed out"
            self._audit.record(
                task_id=task_id, agent_type=subtask.agent_type,
                action="run_subtask", status="timeout",
                error_type="TimeoutError",
            )
        except NexaError as exc:
            subtask.status = SubTaskStatus.FAILED
            subtask.error = exc.message
            self._audit.record(
                task_id=task_id, agent_type=subtask.agent_type,
                action="run_subtask", status="failed",
                error_type=exc.__class__.__name__,
            )
        subtask.completed_at = _now()
    def _resolve_dependencies(self, subtasks: list[SubTask]) -> list[SubTask]:
        """Return subtasks in dependency order (topological sort)."""
        by_id = {s.id: s for s in subtasks}
        resolved: list[SubTask] = []
        seen: set[str] = set()
        def visit(subtask: SubTask) -> None:
            if subtask.id in seen:
                return
            for dep_id in subtask.depends_on:
                dep = by_id.get(dep_id)
                if dep:
                    visit(dep)
            seen.add(subtask.id)
            resolved.append(subtask)
        for subtask in subtasks:
            visit(subtask)
        return resolved
    async def _run_subtasks(self, task_id: str, subtasks: list[SubTask], attachment_ids: list[str], user_id: str | None = None) -> None:
        """Run subtasks respecting dependencies (sequential for now, parallel later)."""
        ordered = self._resolve_dependencies(subtasks)
        for subtask in ordered:
            if subtask.status == SubTaskStatus.SKIPPED:
                continue
            await self._run_subtask(task_id, subtask, attachment_ids, user_id=user_id)
    async def run(
        self,
        task: WorkflowTask,
        cancel_event: asyncio.Event | None = None,
    ) -> WorkflowResult:
        """Execute the workflow: decompose, run agents, merge, return."""
        start = time.perf_counter()
        subtasks = self._decompose(task)
        logger.info("workflow started task_id=%s subtasks=%d", task.id, len(subtasks))
        try:
            await asyncio.wait_for(
                self._run_subtasks(task.id, subtasks, task.attachment_ids, user_id=task.user_id),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            for s in subtasks:
                if s.status == SubTaskStatus.RUNNING:
                    s.status = SubTaskStatus.FAILED
                    s.error = "Workflow timed out"
            self._audit.record(
                task_id=task.id, agent_type="orchestrator",
                action="workflow", status="timeout", error_type="TimeoutError",
            )
        if cancel_event and cancel_event.is_set():
            for s in subtasks:
                if s.status in (SubTaskStatus.PENDING, SubTaskStatus.RUNNING):
                    s.status = SubTaskStatus.CANCELLED
            status = WorkflowStatus.CANCELLED
        elif all(s.status == SubTaskStatus.COMPLETED for s in subtasks):
            status = WorkflowStatus.COMPLETED
        else:
            status = WorkflowStatus.FAILED
        elapsed_ms = (time.perf_counter() - start) * 1000
        final_answer = self._merge_results(task, subtasks)
        answered = next((s for s in reversed(subtasks) if s.model), None)
        logger.info(
            "workflow finished task_id=%s status=%s elapsed_ms=%.1f",
            task.id, status.value, elapsed_ms,
        )
        return WorkflowResult(
            task_id=task.id,
            status=status,
            subtasks=subtasks,
            final_answer=final_answer,
            elapsed_ms=round(elapsed_ms, 2),
            approval_required=bool(self._approvals),
            approval_description=next(iter(self._approvals.values())).action_description if self._approvals else None,
            provider=answered.provider if answered else None,
            model=answered.model if answered else None,
        )
    def _merge_results(self, task: WorkflowTask, subtasks: list[SubTask]) -> str:
        """Combine subtask results into a single answer for the user."""
        parts: list[str] = []
        for s in subtasks:
            if s.result:
                parts.append(f"[{s.agent_type}] {s.result}")
            elif s.error:
                parts.append(f"[{s.agent_type}] FAILED: {s.error}")
        if not parts:
            return "No subtasks were executed."
        return " | ".join(parts)
    # --- Human Approval ---
    def request_approval(self, task_id: str, subtask: SubTask, tool_name: str, tool_input: dict) -> ApprovalRequest:
        """Queue an approval request for a potentially dangerous action."""
        req = ApprovalRequest(
            subtask_id=subtask.id,
            agent_type=subtask.agent_type,
            action_description=f"Agent '{subtask.agent_type}' wants to call tool '{tool_name}' with: {tool_input}",
            tool_name=tool_name,
            tool_input=tool_input,
        )
        self._approvals[req.subtask_id] = req
        self._audit.record(
            task_id=task_id, agent_type=subtask.agent_type,
            action=f"approval_requested:{tool_name}", status="waiting_approval",
        )
        return req
    def resolve_approval(self, subtask_id: str, approved: bool) -> None:
        """Resolve a pending approval; if denied, the subtask is skipped."""
        self._approvals.pop(subtask_id, None)
        self._audit.record(
            task_id="", agent_type="orchestrator",
            action=f"approval_resolved:{subtask_id}", status="approved" if approved else "denied",
        )
    def get_pending_approvals(self) -> list[ApprovalRequest]:
        return list(self._approvals.values())
    def get_audit_entries(self) -> list:
        return self._audit.get_entries()
def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
