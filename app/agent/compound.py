"""Compound multi-deliverable task planning — research + multiple office artifacts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.agent.models import AgentState


class DeliverableKind(str, Enum):
    RESEARCH = "research"
    PRESENTATION = "presentation"
    SPREADSHEET = "spreadsheet"
    DOCUMENT = "document"
    PDF = "pdf"
    PROJECT_FOLDER = "project_folder"


@dataclass(frozen=True)
class Deliverable:
    kind: DeliverableKind
    tool_name: str
    order: int


@dataclass
class CompoundPlan:
    """Ordered deliverables for one user goal."""

    goal: str
    deliverables: list[Deliverable] = field(default_factory=list)
    topic: str = "Project"

    @property
    def is_compound(self) -> bool:
        return len(self.deliverables) >= 2

    def tool_names(self) -> list[str]:
        return [d.tool_name for d in self.deliverables]


_RESEARCH_RE = re.compile(
    r"исследуй|исследован|research|рынок|market\s+research|актуальн|"
    r"источник|startup|стартап|конкурент|look\s+up|найди\s+информац",
    re.IGNORECASE,
)
_PRESENTATION_RE = re.compile(
    r"презентац|powerpoint|\.pptx\b|\bppt\b|слайд|presentation|investor\s+deck",
    re.IGNORECASE,
)
_XLSX_RE = re.compile(
    r"\bxlsx\b|\.xlsx\b|excel|таблиц|spreadsheet|фин(ансов)?\.?\s*модел|"
    r"financial\s+model|бюджет|unit\s+economics",
    re.IGNORECASE,
)
_DOCX_RE = re.compile(
    r"\bdocx\b|\.docx\b|word[\s\-]?[\-–—]?(doc|документ|отч[её]т|report)|"
    r"бизнес[\-\s]?план|business\s+plan|документ\s+word|"
    r"word[\-\s]?отч[её]т|отч[её]т\s+word|word\s+report|"
    r"(?:подготовь|создай|напиши)\s+(?:word[\-\s]?)?отч[её]т",
    re.IGNORECASE,
)
_PDF_RE = re.compile(r"\bpdf\b|\.pdf\b", re.IGNORECASE)
_PROJECT_FOLDER_RE = re.compile(
    r"отдельн\w*\s+папк|папк\w*\s+проект|папк\w*\s+одного\s+проект|"
    r"project\s+folder|сохрани\s+(всё|все|результат)\w*\s+в|"
    r"в\s+папк\w*\s+одного\s+проект",
    re.IGNORECASE,
)
_COMPARISON_TABLE_RE = re.compile(
    r"сравнительн\w*\s+таблиц|таблиц\w*\s+сравнен|comparison\s+table|"
    r"compare\s+\w+\s+in\s+excel|сравни\s+\w+.*excel|xlsx.*сравн",
    re.IGNORECASE,
)
_FINANCIAL_MODEL_RE = re.compile(
    r"фин\w*\s*модел|financial\s+model|unit\s+economics|бюджет|p\s*&\s*l|\bpnl\b",
    re.IGNORECASE,
)

_TOOL = {
    DeliverableKind.RESEARCH: "web_research",
    DeliverableKind.PRESENTATION: "create_presentation",
    DeliverableKind.SPREADSHEET: "create_spreadsheet",
    DeliverableKind.DOCUMENT: "create_document",
    DeliverableKind.PDF: "create_pdf",
    DeliverableKind.PROJECT_FOLDER: "local_files",
}


def build_compound_plan(description: str) -> CompoundPlan:
    """Detect required deliverables and return a stable ordered plan."""
    text = description or ""
    kinds: list[DeliverableKind] = []
    if _RESEARCH_RE.search(text):
        kinds.append(DeliverableKind.RESEARCH)
    if _PRESENTATION_RE.search(text):
        kinds.append(DeliverableKind.PRESENTATION)
    if _XLSX_RE.search(text):
        kinds.append(DeliverableKind.SPREADSHEET)
    if _DOCX_RE.search(text):
        kinds.append(DeliverableKind.DOCUMENT)
    if _PDF_RE.search(text) and DeliverableKind.DOCUMENT not in kinds:
        # Prefer DOCX when both "report" and pdf; PDF only if explicitly asked.
        kinds.append(DeliverableKind.PDF)
    if _PROJECT_FOLDER_RE.search(text) and len(kinds) >= 1:
        kinds.append(DeliverableKind.PROJECT_FOLDER)

    topic = _topic(text)
    deliverables = [
        Deliverable(kind=k, tool_name=_TOOL[k], order=i)
        for i, k in enumerate(kinds)
    ]
    return CompoundPlan(goal=text.strip(), deliverables=deliverables, topic=topic)


# Initial attempt + one retry for recoverable tool failures (no infinite loops).
_MAX_ATTEMPTS_PER_TOOL = 2


def next_deliverable(plan: CompoundPlan, state: AgentState) -> Deliverable | None:
    for item in plan.deliverables:
        if state.has_succeeded(item.tool_name):
            continue
        attempts = _attempt_count(state, item.tool_name)
        if attempts >= _MAX_ATTEMPTS_PER_TOOL:
            # Exhausted retries — keep prior artifacts, move on (partial success).
            continue
        return item
    return None


def _attempt_count(state: AgentState, tool_name: str) -> int:
    return sum(1 for s in state.steps if s.tool_name == tool_name)


def _tool_failed(state: AgentState, tool_name: str) -> bool:
    return (
        any(s.tool_name == tool_name and not s.success for s in state.steps)
        and not state.has_succeeded(tool_name)
    )


def research_context_brief(state: AgentState) -> str:
    """Build labeled FACT / ASSUMPTION brief from web_research output for later tools."""
    output = state.last_successful_output("web_research")
    if not output:
        if _tool_failed(state, "web_research"):
            return (
                "ASSUMPTION: Live web research failed or returned no sources. "
                "Do not invent citations. Use clearly labeled placeholder assumptions only."
            )
        return ""
    if not isinstance(output, dict):
        return f"FACT (tool output):\n{str(output)[:2000]}"

    parts: list[str] = [
        "Research brief for downstream documents. "
        "Label FACT vs ASSUMPTION. Never invent URLs beyond the list below."
    ]
    sources = output.get("sources") or []
    results = output.get("results") or []
    if sources:
        parts.append("FACT — fetched sources:")
        for i, src in enumerate(sources[:5], start=1):
            if isinstance(src, dict):
                title = str(src.get("title") or src.get("url") or f"source-{i}")
                url = str(src.get("url") or "")
                text = str(src.get("text") or "")[:400]
                parts.append(f"[{i}] {title} ({url})\n{text}")
    elif results:
        parts.append("FACT — search snippets (pages may not have been fetched):")
        for i, r in enumerate(results[:5], start=1):
            if isinstance(r, dict):
                parts.append(
                    f"[{i}] {r.get('title', '')} ({r.get('url', '')})\n{r.get('snippet', '')}"
                )
    else:
        parts.append("ASSUMPTION: Research tool returned no usable sources.")
    return "\n".join(parts)[:6000]


def tool_input_for(deliverable: Deliverable, plan: CompoundPlan, state: AgentState) -> dict[str, Any]:
    topic = plan.topic
    brief = research_context_brief(state)
    base_outline = plan.goal
    if brief:
        base_outline = f"{plan.goal}\n\n{brief}"

    if deliverable.kind == DeliverableKind.RESEARCH:
        return {"query": plan.goal, "max_results": 5}

    if deliverable.kind == DeliverableKind.PRESENTATION:
        slide_count = _requested_slide_count(plan.goal)
        deck_title = (
            f"{topic} — Comparison"
            if _COMPARISON_TABLE_RE.search(plan.goal) or _RESEARCH_RE.search(plan.goal)
            else f"{topic} — Overview"
        )
        payload: dict[str, Any] = {
            "title": deck_title,
            "outline": base_outline,
            "source_text": brief or None,
            "filename": f"{_safe_stem(topic)}_deck.pptx",
        }
        if slide_count:
            payload["slide_count"] = slide_count
        return payload

    if deliverable.kind == DeliverableKind.SPREADSHEET:
        # Explicit comparison tables win; otherwise keep the financial-model template
        # (formulas + ASSUMPTION labels) for generic "таблица"/Excel asks.
        if _COMPARISON_TABLE_RE.search(plan.goal) and not _FINANCIAL_MODEL_RE.search(plan.goal):
            rows = _comparison_rows_from_research(state, plan)
            return {
                "title": "Assistant comparison",
                "filename": f"{_safe_stem(topic)}_comparison.xlsx",
                "rows": rows,
                "source_text": brief or "",
            }
        return {
            "title": "Financial model",
            "filename": f"{_safe_stem(topic)}_model.xlsx",
            "financial_model": True,
            "assumptions_note": (
                "ASSUMPTION: Figures below are illustrative placeholders, not researched facts. "
                "Replace with validated numbers before investor use."
            ),
            "source_text": brief or "",
        }

    if deliverable.kind == DeliverableKind.DOCUMENT:
        doc_title = (
            f"{topic} — Research report"
            if _RESEARCH_RE.search(plan.goal)
            else f"{topic} — Document"
        )
        return {
            "title": doc_title,
            "outline": base_outline,
            "source_text": brief or None,
            "filename": f"{_safe_stem(topic)}_report.docx",
        }

    if deliverable.kind == DeliverableKind.PDF:
        return {
            "title": f"{topic} — Report",
            "outline": base_outline,
            "source_text": brief or None,
            "filename": f"{_safe_stem(topic)}_report.pdf",
        }

    if deliverable.kind == DeliverableKind.PROJECT_FOLDER:
        folder = f"projects/{_safe_stem(topic)}"
        links: list[str] = []
        for name in ("create_presentation", "create_spreadsheet", "create_document", "create_pdf"):
            out = state.last_successful_output(name)
            if isinstance(out, dict) and out.get("download_url"):
                links.append(f"- {out.get('filename')}: {out['download_url']}")
        readme = (
            f"# {topic}\n\nGoal: {plan.goal}\n\n## Downloads\n"
            + ("\n".join(links) if links else "(no files yet)")
            + "\n\nASSUMPTION labels apply to any placeholder financial figures.\n"
        )
        return {
            "action": "scaffold_project",
            "path": folder,
            "readme": readme,
        }
    return {}


_KNOWN_ASSISTANTS = (
    "ChatGPT",
    "Claude",
    "Gemini",
    "Copilot",
    "Perplexity",
    "Grok",
    "DeepSeek",
    "Notion AI",
)


def _comparison_rows_from_research(state: AgentState, plan: CompoundPlan) -> list[list[str]]:
    """Build a comparison sheet from research text — no invented prices."""
    brief = research_context_brief(state).lower()
    goal = (plan.goal or "").lower()
    blob = f"{brief}\n{goal}"
    names: list[str] = []
    for name in _KNOWN_ASSISTANTS:
        if name.lower() in blob:
            names.append(name)
    if len(names) < 2:
        # Fall back to five common assistants when research is sparse,
        # but mark capabilities as unverified.
        names = ["ChatGPT", "Claude", "Gemini", "Copilot", "Perplexity"]

    header = [
        "Assistant",
        "Mentioned in sources",
        "Capabilities (from sources)",
        "Limitations (from sources)",
        "Monetization (from sources)",
        "Evidence note",
    ]
    rows: list[list[str]] = [header]
    for name in names[:5]:
        mentioned = "yes" if name.lower() in brief else "no / weak"
        # Keep cells honest — extract short windows rather than inventing metrics.
        caps = _snippet_around(brief, name.lower(), "api|coding|chat|search|vision|tool")
        limits = _snippet_around(brief, name.lower(), "limit|restrict|hallucin|privacy|context")
        money = _snippet_around(brief, name.lower(), "price|subscription|free|plus|pro|api|monetiz|paid")
        rows.append(
            [
                name,
                mentioned,
                caps or "ASSUMPTION: not extracted — see Word report / sources",
                limits or "ASSUMPTION: not extracted — see Word report / sources",
                money or "ASSUMPTION: pricing not verified from fetched pages",
                "Do not treat empty cells as measured facts",
            ]
        )
    rows.append(
        [
            "NOTES",
            "",
            "",
            "",
            "",
            "ASSUMPTION labels required for any number not present in FACT sources",
        ]
    )
    return rows


def _snippet_around(text: str, needle: str, keyword_re: str, *, width: int = 120) -> str:
    if not text or needle not in text:
        return ""
    for m in re.finditer(re.escape(needle), text):
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + width)
        window = text[start:end]
        if re.search(keyword_re, window, re.IGNORECASE):
            clean = re.sub(r"\s+", " ", window).strip()
            return clean[:180]
    # Return a short window even without keyword hit
    idx = text.find(needle)
    window = text[max(0, idx - 20) : idx + 100]
    return re.sub(r"\s+", " ", window).strip()[:160]


def compose_final_answer(plan: CompoundPlan, state: AgentState) -> str:
    lines = [f"Goal: {plan.topic}", ""]
    completed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []

    for d in plan.deliverables:
        if state.has_succeeded(d.tool_name):
            out = state.last_successful_output(d.tool_name)
            completed.append(_format_success(d, out))
        elif _tool_failed(state, d.tool_name):
            err = _last_error(state, d.tool_name) or "failed"
            failed.append(f"- {d.kind.value}: ERROR — {err}")
        else:
            skipped.append(f"- {d.kind.value}: not run")

    if completed:
        lines.append("Completed:")
        lines.extend(completed)
        lines.append("")
    if failed:
        lines.append("Failed (kept prior successful artifacts):")
        lines.extend(failed)
        lines.append("")
    if skipped:
        lines.append("Not started:")
        lines.extend(skipped)
        lines.append("")

    if brief := research_context_brief(state):
        if "ASSUMPTION" in brief and "failed" in brief.lower():
            lines.append(
                "Note: Research did not yield live sources; document numbers are labeled ASSUMPTION."
            )
        elif "FACT" in brief:
            lines.append("Research sources were used where available; assumptions are labeled.")

    if failed and completed:
        lines.append("Status: partial success.")
    elif failed and not completed:
        lines.append("Status: failed.")
    else:
        lines.append("Status: completed.")
    return "\n".join(lines).strip()


def _format_success(d: Deliverable, out: Any) -> str:
    if isinstance(out, dict) and out.get("download_url"):
        return (
            f"- {d.kind.value}: {out.get('filename', d.tool_name)} → {out['download_url']} "
            f"({out.get('summary', 'ok')})"
        )
    if isinstance(out, dict) and d.kind == DeliverableKind.RESEARCH:
        n = len(out.get("sources") or out.get("results") or [])
        return f"- research: {n} source(s)/result(s) collected"
    return f"- {d.kind.value}: ok"


def _last_error(state: AgentState, tool_name: str) -> str | None:
    for step in reversed(state.steps):
        if step.tool_name == tool_name and not step.success:
            return step.error or "unknown error"
    return None


def _topic(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    for pat in (
        r"(?:исследуй|research)\s+(.+?)(?:,|\s+подготов|\s+и\s+созда|\s+сделай|$)",
        r"(?:презентац\w*|business\s+plan|бизнес[\-\s]?план)\s+(?:по\s+|about\s+|про\s+)?(.+)$",
    ):
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            topic = m.group(1).strip(" .,:;")
            topic = re.sub(
                r"\b(powerpoint|pptx|docx|xlsx|pdf|презентац\w*|excel|word)\b",
                "",
                topic,
                flags=re.IGNORECASE,
            ).strip(" .,:;")
            if 3 <= len(topic) <= 90:
                return topic[:90]
    return cleaned[:60] if cleaned else "Project"


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._\-а-яА-ЯёЁ]+", "_", name).strip("_")[:40]
    return stem or "project"


def _requested_slide_count(text: str) -> int | None:
    """Return *content* slide count so title+content ≈ user-requested total."""
    match = re.search(r"(\d{1,2})\s*слайд", text, re.IGNORECASE)
    if not match:
        match = re.search(r"(\d{1,2})\s*slides?\b", text, re.IGNORECASE)
    if not match:
        return None
    total = max(1, min(int(match.group(1)), 20))
    # PPTX builder always adds a title slide first.
    return max(1, total - 1)
