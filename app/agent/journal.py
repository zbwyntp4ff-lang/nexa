"""Structured task execution journal — no secrets, diagnosable latency."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.paths import resolve_under_project_root

_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer\s+[a-z0-9\-._~+/]+=*|password|secret)\s*[:=]\s*\S+"
)


def journal_path() -> Path:
    path = resolve_under_project_root("data/agent_journal.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _scrub(text: str, limit: int = 500) -> str:
    cleaned = _SECRETISH.sub(r"\1=[REDACTED]", text or "")
    return cleaned[:limit]


def record_journal_event(
    *,
    task_id: str,
    event: str,
    tool_name: str | None = None,
    status: str,
    duration_ms: float | None = None,
    attempt: int | None = None,
    error: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one journal line. Never stores tool payloads or user transcripts."""
    row = {
        "id": uuid.uuid4().hex[:16],
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "event": event,
        "tool_name": tool_name,
        "status": status,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "attempt": attempt,
        "error": _scrub(error) if error else None,
        "model": model,
        "provider": provider,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd,
        "meta": meta or {},
    }
    path = journal_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def recent_journal(limit: int = 100, *, task_id: str | None = None) -> list[dict[str, Any]]:
    path = journal_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if task_id and row.get("task_id") != task_id:
            continue
        rows.append(row)
    return rows[-limit:]
