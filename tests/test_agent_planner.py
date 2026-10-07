"""Tests for the RuleBasedPlanner."""
from __future__ import annotations
from app.agent.models import AgentState, AgentStep, AgentStepType, AgentTask, PlannedActionType
from app.agent.planner import RuleBasedPlanner, extract_expression, extract_filename
def _state(description: str, steps: list[AgentStep] | None = None) -> AgentState:
    return AgentState(task=AgentTask(description=description), steps=steps or [])
def test_extract_expression_finds_arithmetic():
    assert extract_expression("Посчитай 25 * 37 и сохрани результат") == "25 * 37"
def test_extract_expression_returns_none_when_absent():
    assert extract_expression("прочитай файл result.txt") is None
def test_extract_filename_finds_explicit_name():
    assert extract_filename("сохрани результат в файл output.txt") == "output.txt"
def test_planner_plans_calculator_first_for_demo_task():
    planner = RuleBasedPlanner()
    action = planner.plan_next(_state("Посчитай 25 * 37 и сохрани результат в файл."))
    assert action.type == PlannedActionType.TOOL_CALL
    assert action.tool_name == "calculator"
    assert action.tool_input["expression"] == "25 * 37"
def test_planner_plans_file_write_after_calculator_succeeds():
    planner = RuleBasedPlanner()
    steps = [
        AgentStep(
            index=0,
            step_type=AgentStepType.TOOL_CALL,
            tool_name="calculator",
            tool_input={"expression": "25 * 37"},
            output=925,
            success=True,
        )
    ]
    action = planner.plan_next(_state("Посчитай 25 * 37 и сохрани результат в файл.", steps))
    assert action.tool_name == "file_write"
    assert action.tool_input["content"] == "925"
def test_planner_returns_final_answer_once_all_capabilities_used():
    planner = RuleBasedPlanner()
    steps = [
        AgentStep(
            index=0, step_type=AgentStepType.TOOL_CALL, tool_name="calculator",
            tool_input={"expression": "25 * 37"}, output=925, success=True,
        ),
        AgentStep(
            index=1, step_type=AgentStepType.TOOL_CALL, tool_name="file_write",
            tool_input={"path": "result.txt", "content": "925"},
            output="Wrote 3 characters", success=True,
        ),
    ]
    action = planner.plan_next(_state("Посчитай 25 * 37 и сохрани результат в файл.", steps))
    assert action.type == PlannedActionType.FINAL_ANSWER
    assert action.final_answer
def test_planner_plans_directory_list_for_listing_task():
    planner = RuleBasedPlanner()
    action = planner.plan_next(_state("Покажи файлы в директории данных"))
    assert action.tool_name == "directory_list"
def test_planner_plans_current_time_for_time_task():
    planner = RuleBasedPlanner()
    action = planner.plan_next(_state("Сколько сейчас времени?"))
    assert action.tool_name == "current_time"
def test_planner_plans_file_read_for_read_task():
    planner = RuleBasedPlanner()
    action = planner.plan_next(_state("Прочитай файл notes.txt"))
    assert action.tool_name == "file_read"
    assert action.tool_input["path"] == "notes.txt"
def test_planner_does_not_repeat_a_tool_that_already_succeeded():
    planner = RuleBasedPlanner()
    steps = [
        AgentStep(
            index=0, step_type=AgentStepType.TOOL_CALL, tool_name="current_time",
            tool_input={}, output="2026-01-01T00:00:00+00:00", success=True,
        )
    ]
    action = planner.plan_next(_state("Сколько сейчас времени?", steps))
    assert action.type == PlannedActionType.FINAL_ANSWER
def test_planner_returns_final_answer_for_task_with_no_recognized_capability():
    planner = RuleBasedPlanner()
    action = planner.plan_next(_state("Расскажи анекдот"))
    assert action.type == PlannedActionType.FINAL_ANSWER
