"""The Executor - runs a planned tool call (or simulates it in dry-run mode)."""
from __future__ import annotations
from app.agent.models import AgentStep, AgentStepType, PlannedAction
from app.core.logging_config import get_logger
from app.models.errors import NexaError
from app.tools.registry import ToolRegistry
logger = get_logger("nexa.agent.executor")
class Executor:
    """Executes a :class:`app.agent.models.PlannedAction` against the tool registry."""
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
    async def execute(self, action: PlannedAction, step_index: int, dry_run: bool) -> AgentStep:
        """Run (or simulate) a single planned tool call and return an ``AgentStep``."""
        if dry_run:
            logger.info(
                "dry-run: would execute tool='%s' input=%s", action.tool_name, action.tool_input
            )
            return AgentStep(
                index=step_index,
                step_type=AgentStepType.TOOL_CALL,
                tool_name=action.tool_name,
                tool_input=action.tool_input,
                output=f"[dry-run] would call '{action.tool_name}' with {action.tool_input}",
                success=True,
                dry_run=True,
            )
        try:
            result = await self._registry.execute(action.tool_name, **action.tool_input)
        except NexaError as exc:
            return AgentStep(
                index=step_index,
                step_type=AgentStepType.ERROR,
                tool_name=action.tool_name,
                tool_input=action.tool_input,
                success=False,
                error=exc.message,
            )
        return AgentStep(
            index=step_index,
            step_type=AgentStepType.TOOL_CALL,
            tool_name=action.tool_name,
            tool_input=action.tool_input,
            output=result.output,
            success=result.success,
            error=result.error,
        )
