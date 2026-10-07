"""Audit log for the Multi-Agent Orchestrator (Part 7).
Records every agent action without storing secrets. Uses the
existing ``app.core.secrets.contains_secret`` to redact.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from app.core.secrets import contains_secret
@dataclass
class AuditEntry:
    timestamp: str
    task_id: str
    agent_type: str
    action: str
    status: str
    duration_ms: float = 0.0
    error_type: str | None = None
    input_summary: str = ""
class AuditLog:
    """Safe audit log — never stores secrets."""
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
    def record(
        self,
        *,
        task_id: str,
        agent_type: str,
        action: str,
        status: str,
        duration_ms: float = 0.0,
        error_type: str | None = None,
        tool_input: dict | None = None,
    ) -> None:
        summary = ""
        if tool_input:
            safe: dict = {}
            for key, value in tool_input.items():
                if isinstance(value, str) and contains_secret(value):
                    safe[key] = "***REDACTED***"
                else:
                    safe[key] = value
            summary = ", ".join(f"{k}={v}" for k, v in list(safe.items())[:3])[:200]
        self._entries.append(
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                task_id=task_id,
                agent_type=agent_type,
                action=action,
                status=status,
                duration_ms=duration_ms,
                error_type=error_type,
                input_summary=summary,
            )
        )
    def get_entries(self) -> list[AuditEntry]:
        return list(self._entries)
    def __len__(self) -> int:
        return len(self._entries)
