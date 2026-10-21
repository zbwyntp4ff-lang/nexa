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
_PRESENTATION_PATTERN: Final = re.compile(
    r"презентац|powerpoint|\.pptx\b|\bppt\b|слайд|presentation|slides?\b",
    re.IGNORECASE,
)
_DOCX_PATTERN: Final = re.compile(
    r"\bdocx\b|\.docx\b|word[\s\-]?(doc|документ)|документ\s+word|"
    r"(создай|сделай|напиши|generate|create).{0,40}(отч[её]т|report)\b",
    re.IGNORECASE,
)
_XLSX_PATTERN: Final = re.compile(
    r"\bxlsx\b|\.xlsx\b|excel|таблиц|spreadsheet|workbook",
    re.IGNORECASE,
)
_PDF_PATTERN: Final = re.compile(
    r"\bpdf\b|\.pdf\b|(создай|сделай|generate|create).{0,30}pdf",
    re.IGNORECASE,
)
_ANALYZE_FILE_PATTERN: Final = re.compile(
    r"проанализируй\s+файл|разбери\s+(файл|документ)|analyze\s+file|inspect\s+document",
    re.IGNORECASE,
)
_BROWSER_PATTERN: Final = re.compile(
    r"открой\s+(сайт|страниц|url)|open\s+(the\s+)?(page|site|url)|browser\s+(open|goto)|"
    r"playwright|зайди\s+на\s+сайт",
    re.IGNORECASE,
)
_OPEN_RESULT_PATTERN: Final = re.compile(
    r"открой\s+(презентац|файл|результат|в\s+powerpoint|в\s+word)|"
    r"open\s+(the\s+)?(presentation|result|file|in\s+powerpoint)",
    re.IGNORECASE,
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

        # Multi-deliverable projects (research + PPTX + XLSX + DOCX, etc.).
        compound = self._plan_compound(state, description)
        if compound is not None:
            return compound

        if _BROWSER_PATTERN.search(description):
            url_match = re.search(r"https?://[^\s]+", description)
            if not url_match:
                return PlannedAction(
                    type=PlannedActionType.FINAL_ANSWER,
                    final_answer="Укажите http(s) URL страницы для browser-инструмента.",
                    rationale="browser needs an explicit URL.",
                )
            return self._plan_simple_tool(
                state,
                tool_name="browser",
                tool_input={"action": "extract", "url": url_match.group(0).rstrip(".,;)")},
                final_answer_builder=lambda output: str(output),
            )

        if _OPEN_RESULT_PATTERN.search(description):
            if not state.has_succeeded("open_result"):
                file_id = None
                for name in ("create_presentation", "create_document", "create_spreadsheet", "create_pdf"):
                    out = state.last_successful_output(name)
                    if isinstance(out, dict) and out.get("file_id"):
                        file_id = out["file_id"]
                        break
                if not file_id:
                    return PlannedAction(
                        type=PlannedActionType.FINAL_ANSWER,
                        final_answer=(
                            "Сначала создайте файл (презентацию/документ), затем попросите открыть его. "
                            "Открытие требует явного подтверждения и локальный desktop (NEXA_LOCAL_DESKTOP=1 / Electron)."
                        ),
                        rationale="open_result needs a prior file_id.",
                    )
                confirmed = bool(
                    re.search(r"confirm|подтверд|да,?\s*открой|open\s+it\s+now", description, re.I)
                )
                if not confirmed:
                    return PlannedAction(
                        type=PlannedActionType.FINAL_ANSWER,
                        final_answer=(
                            f"Файл готов (file_id={file_id}). Чтобы открыть его в приложении по умолчанию, "
                            "повторите запрос с явным подтверждением (например: «да, открой»). "
                            "Я не утверждаю, что PowerPoint установлен, пока это не проверено."
                        ),
                        rationale="open_result waiting for user confirmation.",
                    )
                return PlannedAction(
                    type=PlannedActionType.TOOL_CALL,
                    tool_name="open_result",
                    tool_input={"file_id": file_id, "confirm": True},
                    rationale="User confirmed open_result.",
                )
            output = state.last_successful_output("open_result")
            return PlannedAction(
                type=PlannedActionType.FINAL_ANSWER,
                final_answer=str(output),
                rationale="open_result finished.",
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

        office = self._plan_office_document(state, description)
        if office is not None:
            return office

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

    def _plan_compound(self, state: AgentState, description: str) -> PlannedAction | None:
        """Execute multi-step compound goals without re-running finished tools."""
        from app.agent.compound import (
            build_compound_plan,
            compose_final_answer,
            next_deliverable,
            tool_input_for,
        )

        plan = build_compound_plan(description)
        if not plan.is_compound:
            return None

        nxt = next_deliverable(plan, state)
        if nxt is not None:
            return PlannedAction(
                type=PlannedActionType.TOOL_CALL,
                tool_name=nxt.tool_name,
                tool_input=tool_input_for(nxt, plan, state),
                rationale=f"Compound plan step: {nxt.kind.value} ({nxt.tool_name}).",
            )
        return PlannedAction(
            type=PlannedActionType.FINAL_ANSWER,
            final_answer=compose_final_answer(plan, state),
            rationale="All compound deliverables attempted.",
        )

    def _plan_office_document(self, state: AgentState, description: str) -> PlannedAction | None:
        """Route natural-language document requests to office generation tools."""
        if _ANALYZE_FILE_PATTERN.search(description):
            filename = extract_filename(description)
            if not filename:
                return PlannedAction(
                    type=PlannedActionType.FINAL_ANSWER,
                    final_answer="Укажите путь к файлу в рабочей области агента (например: notes.pdf).",
                    rationale="analyze_file needs an explicit filename.",
                )
            return self._plan_simple_tool(
                state,
                tool_name="analyze_file",
                tool_input={"path": filename},
                final_answer_builder=_office_final_answer,
            )

        # Prefer the most specific format keyword (pptx before pdf/docx).
        if _PRESENTATION_PATTERN.search(description):
            title = _extract_topic_title(description) or "Presentation"
            return self._plan_simple_tool(
                state,
                tool_name="create_presentation",
                tool_input={
                    "title": title,
                    "outline": description,
                    "filename": extract_filename(description) or f"{title}.pptx",
                },
                final_answer_builder=_office_final_answer,
            )

        if _XLSX_PATTERN.search(description) and not _PRESENTATION_PATTERN.search(description):
            title = _extract_topic_title(description) or "Spreadsheet"
            return self._plan_simple_tool(
                state,
                tool_name="create_spreadsheet",
                tool_input={
                    "title": title,
                    "csv_text": _default_sheet_csv(description),
                    "filename": extract_filename(description) or f"{title}.xlsx",
                },
                final_answer_builder=_office_final_answer,
            )

        if _PDF_PATTERN.search(description):
            title = _extract_topic_title(description) or "Report"
            return self._plan_simple_tool(
                state,
                tool_name="create_pdf",
                tool_input={
                    "title": title,
                    "outline": description,
                    "filename": extract_filename(description) or f"{title}.pdf",
                },
                final_answer_builder=_office_final_answer,
            )

        if _DOCX_PATTERN.search(description):
            title = _extract_topic_title(description) or "Document"
            return self._plan_simple_tool(
                state,
                tool_name="create_document",
                tool_input={
                    "title": title,
                    "outline": description,
                    "filename": extract_filename(description) or f"{title}.docx",
                },
                final_answer_builder=_office_final_answer,
            )
        return None

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


def _office_final_answer(output) -> str:
    """Human-readable answer with download URL — never a raw server path."""
    if isinstance(output, dict):
        url = output.get("download_url") or ""
        name = output.get("filename") or "file"
        summary = output.get("summary") or "File created."
        slides = output.get("slides")
        extra = f" Slides: {slides}." if isinstance(slides, int) else ""
        if url:
            return f"{summary}{extra} Download: {url} ({name}). File is ready — open it in the matching app on your device."
        return f"{summary}{extra}"
    return str(output)


_TOPIC_PATTERNS: Final = (
    re.compile(
        r"(?:презентац\w*|presentation|документ|отч[её]т|report|таблиц\w*|pdf)\s+"
        r"(?:по\s+|about\s+|on\s+|про\s+)?(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"(?:сделай|создай|generate|create)\s+(?:мне\s+)?(.+?)(?:\s+и\s+перенес|\s+в\s+powerpoint|\s+pptx|$)",
        re.IGNORECASE | re.DOTALL,
    ),
)


def _extract_topic_title(description: str) -> str | None:
    text = description.strip()
    for pattern in _TOPIC_PATTERNS:
        match = pattern.search(text)
        if match:
            topic = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;")
            topic = re.sub(
                r"\b(powerpoint|pptx|docx|xlsx|pdf|презентац\w*|слайд\w*)\b",
                "",
                topic,
                flags=re.IGNORECASE,
            ).strip(" .,:;")
            if 2 <= len(topic) <= 80:
                return topic[:80]
    return None


def _default_sheet_csv(description: str) -> str:
    """Minimal starter table when the user did not supply rows."""
    topic = _extract_topic_title(description) or "Item"
    return f"Item,Value,Notes\n{topic},1,Generated by NEXA\nFollow-up,2,Edit as needed\n"


# Backwards-compatible alias used by app/agent/agent.py's type hint.
Planner = RuleBasedPlanner
