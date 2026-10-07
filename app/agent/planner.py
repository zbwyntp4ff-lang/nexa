"""Rule-based planner for the agent loop (Part 2).

Deterministic regex/keyword based planning: given the current
:class:`AgentState`, decide the next action - either a tool call or a
final answer - without calling a model. See ``app/agent/agent.py`` for
how an optional Model Gateway call is layered on top of a FINAL_ANSWER
action when no tool fully answered the task.
"""
from __future__ import annotations

import re
from typing import Final

from app.agent.models import AgentState, PlannedAction, PlannedActionType

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_ARITHMETIC_PATTERN: Final = re.compile(
    r"(-?\d+(?:[.,]\d+)?\s*[+\-*/]\s*-?\d+(?:[.,]\d+)?"
    r"(?:\s*[+\-*/]\s*-?\d+(?:[.,]\d+)?)*)"
)
_SAVE_PATTERN: Final = re.compile(r"сохран|save", re.IGNORECASE)
_READ_PATTERN: Final = re.compile(r"прочита|прочти|открой файл|read file", re.IGNORECASE)
_CREATE_FILE_PATTERN: Final = re.compile(r"созда[йн].{0,3}файл|create file", re.IGNORECASE)
_CREATE_DIR_PATTERN: Final = re.compile(
    r"созда[йн].{0,3}(?:директори|папк)|create (?:directory|folder)", re.IGNORECASE
)
_RENAME_PATTERN: Final = re.compile(r"переименуй|rename", re.IGNORECASE)
_LIST_PATTERN: Final = re.compile(
    r"покажи файлы|список файлов|файлы в директории|list files|директори", re.IGNORECASE
)
_TIME_PATTERN: Final = re.compile(
    r"сколько.{0,10}времени|текущее время|какое сейчас время|current time|what time", re.IGNORECASE
)
_WEB_RESEARCH_PATTERN: Final = re.compile(
    r"найди в интернете|поищи в интернете|поищи в сети|search the web|search online", re.IGNORECASE
)
_BUILD_PROJECT_PATTERN: Final = re.compile(
    r"(создай|сделай|собери)\s+(мне\s+)?(?:\S+\s+){0,4}(игру|сайт|приложен|инструмент|прототип)|"
    r"create\s+(an?\s+)?(?:\S+\s+){0,4}(app|game|website|site|tool)|"
    r"build\s+(an?\s+)?(?:\S+\s+){0,4}(app|game|website|site)",
    re.IGNORECASE,
)
_FILENAME_PATTERN: Final = re.compile(r"файл\w*\s+([^\s,;:]+\.[A-Za-zА-Яа-я0-9]+)", re.IGNORECASE)
_DIRECTORY_PATTERN: Final = re.compile(r"(?:директори\w*|папк\w*)\s+([^\s,;:]+)", re.IGNORECASE)


def extract_expression(text: str) -> str | None:
    """Return the first simple arithmetic expression found in ``text``, if any."""
    match = _ARITHMETIC_PATTERN.search(text)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def extract_filename(text: str) -> str | None:
    """Return an explicit filename mentioned in ``text`` (after the word "файл"), if any."""
    match = _FILENAME_PATTERN.search(text)
    if not match:
        return None
    return match.group(1).rstrip(".,;:")


def extract_directory(text: str) -> str | None:
    """Return an explicit directory name mentioned in ``text``, if any."""
    match = _DIRECTORY_PATTERN.search(text)
    if not match:
        return None
    return match.group(1).rstrip(".,;:")


class RuleBasedPlanner:
    """Deterministic, regex/keyword based implementation of the agent planner."""

    def plan_next(self, state: AgentState) -> PlannedAction:
        description = state.task.description

        expression = extract_expression(description)
        if expression is not None:
            return self._plan_arithmetic(state, description, expression)

        if _LIST_PATTERN.search(description):
            return self._plan_simple_tool(
                state,
                tool_name="directory_list",
                tool_input={"path": extract_directory(description) or "."},
                final_answer_builder=lambda output: f"Files: {output}",
            )

        if _TIME_PATTERN.search(description):
            return self._plan_simple_tool(
                state,
                tool_name="current_time",
                tool_input={},
                final_answer_builder=lambda output: f"Current time: {output}",
            )

        if _READ_PATTERN.search(description):
            filename = extract_filename(description)
            if filename:
                return self._plan_simple_tool(
                    state,
                    tool_name="file_read",
                    tool_input={"path": filename},
                    final_answer_builder=lambda output: str(output),
                )

        if _CREATE_DIR_PATTERN.search(description):
            directory = extract_directory(description) or "new_folder"
            return self._plan_simple_tool(
                state,
                tool_name="directory_create",
                tool_input={"path": directory},
                final_answer_builder=lambda output: str(output),
            )

        if _CREATE_FILE_PATTERN.search(description):
            filename = extract_filename(description) or "new_file.txt"
            return self._plan_simple_tool(
                state,
                tool_name="file_create",
                tool_input={"path": filename, "content": ""},
                final_answer_builder=lambda output: str(output),
            )

        if _RENAME_PATTERN.search(description):
            return PlannedAction(
                type=PlannedActionType.FINAL_ANSWER,
                final_answer="Rename requires both an old and a new path; please specify them explicitly.",
                rationale="Rename pattern matched but could not unambiguously extract both paths.",
            )

        if _WEB_RESEARCH_PATTERN.search(description):
            if not state.has_succeeded("web_research"):
                return PlannedAction(
                    type=PlannedActionType.TOOL_CALL,
                    tool_name="web_research",
                    tool_input={"query": description},
                    rationale="Task asks for web research.",
                )
            output = state.last_successful_output("web_research")
            return PlannedAction(
                type=PlannedActionType.FINAL_ANSWER,
                final_answer=str(output),
                rationale="Web research already completed.",
            )

        # Build Engine: project creation is model-planned, but we force a workspace
        # scaffold first so follow-up synthesis can write real files (not samples).
        if _BUILD_PROJECT_PATTERN.search(description):
            if not state.has_succeeded("directory_create"):
                return PlannedAction(
                    type=PlannedActionType.TOOL_CALL,
                    tool_name="directory_create",
                    tool_input={"path": "project"},
                    rationale="Build request: create project workspace before generating files.",
                )
            return PlannedAction(
                type=PlannedActionType.FINAL_ANSWER,
                final_answer=None,
                rationale="Project folder ready; defer to model+file tools via gateway synthesis.",
            )

        return PlannedAction(
            type=PlannedActionType.FINAL_ANSWER,
            final_answer=None,
            rationale="No rule-based capability matched this task; deferring to the model.",
        )

    def _plan_arithmetic(self, state: AgentState, description: str, expression: str) -> PlannedAction:
        if not state.has_succeeded("calculator"):
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL,
                tool_name="calculator",
                tool_input={"expression": expression},
                rationale="Task contains an arithmetic expression.",
            )
        result = state.last_successful_output("calculator")
        if _SAVE_PATTERN.search(description):
            if not state.has_succeeded("file_write"):
                filename = extract_filename(description) or "result.txt"
                return PlannedAction(
                    type=PlannedActionType.TOOL_CALL,
                    tool_name="file_write",
                    tool_input={"path": filename, "content": str(result)},
                    rationale="Calculator succeeded; task also asks to save the result.",
                )
            return PlannedAction(
                type=PlannedActionType.FINAL_ANSWER,
                final_answer=f"Result: {result}",
                rationale="Calculator and file_write both succeeded.",
            )
        return PlannedAction(
            type=PlannedActionType.FINAL_ANSWER,
            final_answer=f"Result: {result}",
            rationale="Calculator succeeded; no save requested.",
        )

    @staticmethod
    def _plan_simple_tool(state: AgentState, *, tool_name: str, tool_input: dict, final_answer_builder) -> PlannedAction:
        if not state.has_succeeded(tool_name):
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL,
                tool_name=tool_name,
                tool_input=tool_input,
                rationale=f"Task matched the '{tool_name}' capability.",
            )
        output = state.last_successful_output(tool_name)
        return PlannedAction(
            type=PlannedActionType.FINAL_ANSWER,
            final_answer=final_answer_builder(output),
            rationale=f"'{tool_name}' already succeeded.",
        )


# Backwards-compatible alias used by app/agent/agent.py's type hint.
Planner = RuleBasedPlanner
