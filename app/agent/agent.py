"""``Agent`` - the orchestration loop tying Planner, Tool Selector, Executor
and Verifier together.
Architecture::
    User -> Agent -> Planner -> (Model) -> Tool Selector -> Tool
          -> Observation -> Verifier -> [loop] -> Final Answer
Safety rails against infinite loops / runaway execution:
- ``MAX_STEPS``: hard cap on the number of tool-call steps in one run.
- ``TIMEOUT``: hard wall-clock cap on the whole run.
- ``ERROR_LIMIT``: stop once too many steps have failed verification.
- ``CANCELLATION``: cooperative cancellation via an ``asyncio.Event``.
- ``dry_run``: simulate the whole plan without any real side effects.
"""
from __future__ import annotations
import asyncio
import time
from app.agent.executor import Executor
from app.agent.models import (
    AgentResult,
    AgentState,
    AgentStatus,
    AgentStep,
    AgentStepType,
    AgentTask,
    PlannedActionType,
)
from app.agent.planner import Planner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.core.logging_config import get_logger
from app.gateway.policy import infer_task_kind
from app.models.chat import ChatMessage, ChatRole
from app.models.errors import AgentTaskError, NexaError
logger = get_logger("nexa.agent")
def _bounded(value, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "... (truncated)"
DEFAULT_MAX_STEPS = 10
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_ERROR_LIMIT = 3
# Tool outputs (e.g. full fetched web pages) can be large; bound how much of
# them is folded into a model prompt so a slow/local model isn't handed an
# unbounded amount of text.
MAX_TOOL_SUMMARY_CHARS = 3_000
class Agent:
    """Runs an :class:`AgentTask` to completion (or a defined stop condition)."""
    def __init__(
        self,
        planner: Planner,
        tool_selector: ToolSelector,
        executor: Executor,
        verifier: Verifier,
        max_steps: int = DEFAULT_MAX_STEPS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        error_limit: int = DEFAULT_ERROR_LIMIT,
        model_gateway=None,
    ) -> None:
        self._planner = planner
        self._tool_selector = tool_selector
        self._executor = executor
        self._verifier = verifier
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.error_limit = error_limit
        # Optional. The agent calls ModelGateway.chat and never sees a provider SDK.
        self._model_gateway = model_gateway
        self._model_provider: str | None = None
        self._model_id: str | None = None
        self._model_display: str | None = None
    async def run(
        self, task: AgentTask, cancel_event: asyncio.Event | None = None
    ) -> AgentResult:
        """Execute ``task`` to completion or until a stop condition triggers.
        Raises:
            app.models.errors.AgentTaskError: If the task description is empty.
        """
        if not task.description or not task.description.strip():
            raise AgentTaskError("Agent task description must not be empty.")
        state = AgentState(task=task)
        self._model_provider = None
        self._model_id = None
        self._model_display = None
        start = time.perf_counter()
        logger.info(
            "agent run started task_id=%s dry_run=%s max_steps=%d timeout=%.1f error_limit=%d",
            task.id,
            task.dry_run,
            self.max_steps,
            self.timeout_seconds,
            self.error_limit,
        )
        try:
            await asyncio.wait_for(
                self._run_loop(state, cancel_event), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            state.status = AgentStatus.TIMEOUT
        elapsed_ms = (time.perf_counter() - start) * 1000
        final_answer = self._extract_final_answer(state)
        success = state.status == AgentStatus.COMPLETED
        logger.info(
            "agent run finished task_id=%s status=%s steps=%d elapsed_ms=%.1f",
            task.id,
            state.status.value,
            len(state.steps),
            elapsed_ms,
        )
        return AgentResult(
            task_id=task.id,
            status=state.status,
            success=success,
            final_answer=final_answer,
            steps=state.steps,
            elapsed_ms=round(elapsed_ms, 2),
            dry_run=task.dry_run,
            provider=self._model_provider,
            model=self._model_id,
            display_name=self._model_display,
        )
    async def _run_loop(self, state: AgentState, cancel_event: asyncio.Event | None) -> None:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                state.status = AgentStatus.CANCELLED
                return
            if len(state.steps) >= self.max_steps:
                state.status = AgentStatus.MAX_STEPS_EXCEEDED
                return
            if state.error_count >= self.error_limit:
                state.status = AgentStatus.ERROR_LIMIT_EXCEEDED
                return
            action = self._planner.plan_next(state)
            if action.type == PlannedActionType.FINAL_ANSWER:
                action = await self._maybe_ask_model(state, action)
            if action.type == PlannedActionType.FINAL_ANSWER:
                state.steps.append(
                    AgentStep(
                        index=len(state.steps),
                        step_type=AgentStepType.FINAL_ANSWER,
                        output=action.final_answer,
                        success=True,
                    )
                )
                state.status = AgentStatus.COMPLETED
                return
            if action.tool_name in state.task.disabled_tools:
                state.steps.append(
                    AgentStep(
                        index=len(state.steps),
                        step_type=AgentStepType.ERROR,
                        tool_name=action.tool_name,
                        tool_input=action.tool_input,
                        success=False,
                        error=f"The '{action.tool_name}' plugin is turned off in Settings -> Plugins.",
                    )
                )
                state.error_count += 1
                continue
            try:
                self._tool_selector.select(action.tool_name)
            except NexaError as exc:
                state.steps.append(
                    AgentStep(
                        index=len(state.steps),
                        step_type=AgentStepType.ERROR,
                        tool_name=action.tool_name,
                        tool_input=action.tool_input,
                        success=False,
                        error=exc.message,
                    )
                )
                state.error_count += 1
                continue
            step = await self._executor.execute(
                action, step_index=len(state.steps), dry_run=state.task.dry_run
            )
            verified = await self._verifier.verify_step(step)
            if not step.success or not verified:
                state.error_count += 1
                if step.success and not verified:
                    step = step.model_copy(
                        update={
                            "success": False,
                            "error": step.error or "Verification failed after tool execution.",
                        }
                    )
            state.steps.append(step)
            # Yield control so cancellation / other tasks can be observed
            # promptly between steps even for fast, CPU-only tool chains.
            await asyncio.sleep(0)
    async def _maybe_ask_model(self, state: AgentState, action):
        """Ask the Model Gateway when no tool produced the answer, or when
        extra context (e.g. a document excerpt) needs to be synthesized with
        a tool result into one answer.
        The agent never imports a concrete provider, and never receives
        image bytes - ``context`` is always plain text handed to it by the
        caller (e.g. the Orchestrator), so the agent stays unaware of where
        that text came from.
        """
        if self._model_gateway is None or state.task.dry_run:
            return action
        context = (state.task.context or "").strip()
        used_tool = any(
            step.step_type == AgentStepType.TOOL_CALL and step.success for step in state.steps
        )
        if used_tool and not context:
            return action
        content = state.task.description
        if used_tool:
            tool_summary = "; ".join(
                f"{step.tool_name} -> {_bounded(step.output, MAX_TOOL_SUMMARY_CHARS)}"
                for step in state.steps
                if step.step_type == AgentStepType.TOOL_CALL and step.success
            )
            content += f"\n\nTool results so far:\n{_bounded(tool_summary, MAX_TOOL_SUMMARY_CHARS)}"
        if context:
            content += f"\n\nAdditional context:\n{context}"
        kind = infer_task_kind(state.task.description)
        messages = [ChatMessage(role=ChatRole.USER, content=content)]
        try:
            from app.knowledge_core.composer import KnowledgeCoreComposer

            core = KnowledgeCoreComposer().compose(state.task.description, task=kind.value)
            if core.text:
                messages = [
                    ChatMessage(role=ChatRole.SYSTEM, content=core.text),
                    *messages,
                ]
        except Exception:  # noqa: BLE001 - agent must still answer without Knowledge Core
            pass
        result = await self._model_gateway.chat(messages, task_kind=kind)
        self._model_provider = result.provider
        self._model_id = result.model_id
        self._model_display = result.display_name
        logger.info(
            "agent model answer provider=%s model=%s task=%s combined_context=%s",
            result.provider,
            result.model_id,
            kind.value,
            bool(context),
        )
        return action.model_copy(update={"final_answer": result.text, "rationale": "Answered by the model gateway."})
    @staticmethod
    def _extract_final_answer(state: AgentState) -> str | None:
        for step in reversed(state.steps):
            if step.step_type == AgentStepType.FINAL_ANSWER:
                return step.output
        if state.status == AgentStatus.TIMEOUT:
            return None
        return None
