"""Integration tests for the Agent orchestration loop: tool selection,
execution, verification, MAX_STEPS/TIMEOUT/ERROR_LIMIT/CANCELLATION, and the
Part 2 demo scenario.
"""
from __future__ import annotations
import asyncio
import pytest
from app.agent.agent import Agent
from app.agent.executor import Executor
from app.agent.models import (
    AgentState,
    AgentStatus,
    AgentTask,
    PlannedAction,
    PlannedActionType,
)
from app.agent.planner import Planner, RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.models.errors import AgentTaskError
from app.tools.base import Tool, ToolResult
from app.tools.calculator import CalculatorTool
from app.tools.current_time import CurrentTimeTool
from app.tools.directory_list import DirectoryListTool
from app.tools.file_read import FileReadTool
from app.tools.file_write import FileWriteTool
from app.tools.registry import ToolRegistry
def _build_registry(tmp_path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    registry.register(FileReadTool(tmp_path))
    registry.register(FileWriteTool(tmp_path))
    registry.register(DirectoryListTool(tmp_path))
    return registry
def _build_agent(tmp_path, planner: Planner | None = None, **agent_kwargs) -> Agent:
    registry = _build_registry(tmp_path)
    return Agent(
        planner=planner or RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        **agent_kwargs,
    )
# --- Demo scenario -----------------------------------------------------------
async def test_demo_task_calculates_and_saves_result(tmp_path):
    agent = _build_agent(tmp_path)
    task = AgentTask(description="Посчитай 25 * 37 и сохрани результат в файл.")
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert result.success is True
    tool_calls = [s for s in result.steps if s.tool_name]
    assert [s.tool_name for s in tool_calls] == ["calculator", "file_write"]
    assert tool_calls[0].output == 925
    assert tool_calls[1].success is True
    assert (tmp_path / "result.txt").read_text() == "925"
    assert "925" in result.final_answer
async def test_demo_task_dry_run_has_no_side_effects(tmp_path):
    agent = _build_agent(tmp_path)
    task = AgentTask(description="Посчитай 25 * 37 и сохрани результат в файл.", dry_run=True)
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert result.dry_run is True
    assert not (tmp_path / "result.txt").exists()
    assert all(s.dry_run for s in result.steps if s.tool_name)
# --- Tool selection -----------------------------------------------------------
async def test_agent_selects_current_time_tool_for_time_task(tmp_path):
    agent = _build_agent(tmp_path)
    result = await agent.run(AgentTask(description="Сколько сейчас времени?"))
    assert result.status == AgentStatus.COMPLETED
    tool_names = [s.tool_name for s in result.steps if s.tool_name]
    assert tool_names == ["current_time"]
async def test_agent_refuses_disabled_tool_with_a_clear_error_step(tmp_path):
    agent = _build_agent(tmp_path)
    task = AgentTask(
        description="Посчитай 25 * 37 и сохрани результат в файл.",
        disabled_tools=frozenset({"calculator"}),
    )
    result = await agent.run(task)
    calc_step = next(s for s in result.steps if s.tool_name == "calculator")
    assert calc_step.success is False
    assert "plugin is turned off" in calc_step.error
async def test_agent_tool_selection_fails_for_unregistered_tool(tmp_path):
    class _BrokenPlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            if state.steps:
                return PlannedAction(type=PlannedActionType.FINAL_ANSWER, final_answer="done")
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL, tool_name="not_a_real_tool", tool_input={}
            )
    agent = _build_agent(tmp_path, planner=_BrokenPlanner())
    result = await agent.run(AgentTask(description="anything"))
    assert any(not s.success for s in result.steps)
    assert result.status == AgentStatus.COMPLETED  # recovers and still finalizes
# --- Execution -----------------------------------------------------------------
async def test_agent_executes_tool_and_records_observation(tmp_path):
    agent = _build_agent(tmp_path)
    result = await agent.run(AgentTask(description="Посчитай 100 / 4"))
    calc_step = next(s for s in result.steps if s.tool_name == "calculator")
    assert calc_step.output == 25.0
    assert calc_step.success is True
# --- Verification -----------------------------------------------------------
async def test_verifier_detects_file_write_content_mismatch(tmp_path):
    registry = _build_registry(tmp_path)
    verifier = Verifier(registry)
    from app.agent.models import AgentStep, AgentStepType
    await registry.execute("file_write", path="result.txt", content="925")
    # Simulate a step that *claims* different content than what is on disk.
    mismatched_step = AgentStep(
        index=0,
        step_type=AgentStepType.TOOL_CALL,
        tool_name="file_write",
        tool_input={"path": "result.txt", "content": "999"},
        output="Wrote 3 characters",
        success=True,
    )
    assert await verifier.verify_step(mismatched_step) is False
async def test_verifier_accepts_matching_file_write(tmp_path):
    registry = _build_registry(tmp_path)
    verifier = Verifier(registry)
    from app.agent.models import AgentStep, AgentStepType
    await registry.execute("file_write", path="result.txt", content="925")
    step = AgentStep(
        index=0,
        step_type=AgentStepType.TOOL_CALL,
        tool_name="file_write",
        tool_input={"path": "result.txt", "content": "925"},
        output="Wrote 3 characters",
        success=True,
    )
    assert await verifier.verify_step(step) is True
async def test_agent_counts_verification_failure_as_an_error(tmp_path):
    class _AlwaysClaimWrongContentPlanner(Planner):
        """Plans a file_write whose declared content never matches reality."""
        def __init__(self) -> None:
            self._calls = 0
        def plan_next(self, state: AgentState) -> PlannedAction:
            self._calls += 1
            if self._calls > 3:
                return PlannedAction(type=PlannedActionType.FINAL_ANSWER, final_answer="done")
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL,
                tool_name="file_write",
                tool_input={"path": "out.txt", "content": f"claim-{self._calls}"},
            )
    # The tool always actually writes "actual" regardless of requested content,
    # so verification (which reads the file back) will always disagree.
    class _LyingFileWriteTool(Tool):
        name = "file_write"
        description = "writes something different than requested"
        input_schema = {}
        permissions = frozenset({"filesystem:write"})
        async def execute(self, **kwargs) -> ToolResult:
            (tmp_path / kwargs["path"]).write_text("actual-content")
            return ToolResult(success=True, output="wrote")
    registry = ToolRegistry()
    registry.register(_LyingFileWriteTool())
    registry.register(FileReadTool(tmp_path))
    agent = Agent(
        planner=_AlwaysClaimWrongContentPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        error_limit=2,
    )
    result = await agent.run(AgentTask(description="anything"))
    assert result.status == AgentStatus.ERROR_LIMIT_EXCEEDED
    assert all(not s.success for s in result.steps)
# --- MAX_STEPS -----------------------------------------------------------------
async def test_concurrent_agent_loops_keep_per_run_budgets_isolated(tmp_path):
    class _InfinitePlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL,
                tool_name="current_time",
                tool_input={},
            )

    agent = _build_agent(
        tmp_path,
        planner=_InfinitePlanner(),
        max_steps=9,
        error_limit=100,
    )
    short_run = AgentState(task=AgentTask(description="short run"))
    long_run = AgentState(task=AgentTask(description="long run"))

    await asyncio.gather(
        agent._run_loop(short_run, None, max_steps=1, error_limit=100),
        agent._run_loop(long_run, None, max_steps=3, error_limit=100),
    )

    assert short_run.status == AgentStatus.MAX_STEPS_EXCEEDED
    assert len(short_run.steps) == 1
    assert long_run.status == AgentStatus.MAX_STEPS_EXCEEDED
    assert len(long_run.steps) == 3
    # Per-run limits must never mutate the cached Agent's defaults.
    assert agent.max_steps == 9
    assert agent.error_limit == 100


async def test_agent_stops_at_max_steps_to_prevent_infinite_loops(tmp_path):
    class _InfinitePlanner(Planner):
        """Always asks for the current time again - never reports success as
        'done' from the agent's point of view, simulating a planner bug that
        would otherwise loop forever."""
        def plan_next(self, state: AgentState) -> PlannedAction:
            return PlannedAction(type=PlannedActionType.TOOL_CALL, tool_name="current_time", tool_input={})
    agent = _build_agent(tmp_path, planner=_InfinitePlanner(), max_steps=5, error_limit=1000)
    result = await agent.run(AgentTask(description="loop forever"))
    assert result.status == AgentStatus.MAX_STEPS_EXCEEDED
    assert len(result.steps) == 5
    assert result.success is False
# --- ERROR_LIMIT -----------------------------------------------------------------
async def test_agent_stops_after_error_limit_exceeded(tmp_path):
    class _AlwaysFailingPlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL,
                tool_name="calculator",
                tool_input={"expression": "not-a-valid-expression"},
            )
    agent = _build_agent(tmp_path, planner=_AlwaysFailingPlanner(), max_steps=100, error_limit=3)
    result = await agent.run(AgentTask(description="always fails"))
    assert result.status == AgentStatus.ERROR_LIMIT_EXCEEDED
    assert len(result.steps) == 3
    assert all(not s.success for s in result.steps)
    assert result.success is False
# --- TIMEOUT -----------------------------------------------------------------
async def test_agent_times_out_on_slow_tool(tmp_path):
    class _SlowTool(Tool):
        name = "slow"
        description = "sleeps forever"
        input_schema = {}
        permissions = frozenset()
        async def execute(self, **kwargs) -> ToolResult:
            await asyncio.sleep(5)
            return ToolResult(success=True, output="too late")
    class _SlowPlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            return PlannedAction(type=PlannedActionType.TOOL_CALL, tool_name="slow", tool_input={})
    registry = ToolRegistry()
    registry.register(_SlowTool())
    agent = Agent(
        planner=_SlowPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        timeout_seconds=0.05,
    )
    result = await agent.run(AgentTask(description="slow task"))
    assert result.status == AgentStatus.TIMEOUT
    assert result.success is False
# --- CANCELLATION -----------------------------------------------------------------
async def test_agent_stops_immediately_when_cancelled(tmp_path):
    class _InfinitePlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            return PlannedAction(type=PlannedActionType.TOOL_CALL, tool_name="current_time", tool_input={})
    cancel_event = asyncio.Event()
    cancel_event.set()
    agent = _build_agent(tmp_path, planner=_InfinitePlanner(), max_steps=1000)
    result = await agent.run(AgentTask(description="cancel me"), cancel_event=cancel_event)
    assert result.status == AgentStatus.CANCELLED
    assert len(result.steps) == 0
    assert result.success is False
async def test_agent_cancels_mid_run(tmp_path):
    class _InfinitePlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            return PlannedAction(type=PlannedActionType.TOOL_CALL, tool_name="current_time", tool_input={})
    cancel_event = asyncio.Event()
    agent = _build_agent(tmp_path, planner=_InfinitePlanner(), max_steps=1000, error_limit=1000)
    async def _cancel_soon():
        await asyncio.sleep(0.01)
        cancel_event.set()
    cancel_task = asyncio.create_task(_cancel_soon())
    result = await agent.run(AgentTask(description="cancel mid-run"), cancel_event=cancel_event)
    await cancel_task
    assert result.status == AgentStatus.CANCELLED
    assert result.success is False
# --- Errors -----------------------------------------------------------------
async def test_agent_rejects_empty_task_description(tmp_path):
    agent = _build_agent(tmp_path)
    with pytest.raises(AgentTaskError):
        await agent.run(AgentTask(description="   "))

async def test_agent_model_context_is_restored_when_run_raises(tmp_path):
    from app.agent.agent import _RUN_MODEL_PROVIDER, _RUN_MODEL_ID, _RUN_MODEL_DISPLAY

    class _ExplodingPlanner(Planner):
        def plan_next(self, state: AgentState) -> PlannedAction:
            raise RuntimeError("simulated planner failure")

    agent = _build_agent(tmp_path, planner=_ExplodingPlanner())
    provider_token = _RUN_MODEL_PROVIDER.set("outer-provider")
    model_token = _RUN_MODEL_ID.set("outer-model")
    display_token = _RUN_MODEL_DISPLAY.set("outer-display")
    try:
        with pytest.raises(RuntimeError, match="simulated planner failure"):
            await agent.run(AgentTask(description="trigger failure"))
        assert _RUN_MODEL_PROVIDER.get() == "outer-provider"
        assert _RUN_MODEL_ID.get() == "outer-model"
        assert _RUN_MODEL_DISPLAY.get() == "outer-display"
    finally:
        _RUN_MODEL_PROVIDER.reset(provider_token)
        _RUN_MODEL_ID.reset(model_token)
        _RUN_MODEL_DISPLAY.reset(display_token)

