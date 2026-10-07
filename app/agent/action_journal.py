"""Action journal for the Agent — logs every tool call without storing secrets.
The journal is in-memory (per agent run) and never persists secrets. It's
used for audit/debugging, not for replay.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from app.core.secrets import contains_secret
@dataclass
class JournalEntry:
    timestamp: str
    tool_name: str
    input_summary: str
    success: bool
    error: str | None = None
class ActionJournal:
    """Records what the agent did, without storing secrets."""
    def __init__(self) -> None:
        self._entries: list[JournalEntry] = []
    def record(self, tool_name: str, tool_input: dict, success: bool, error: str | None = None) -> None:
        # Redact any secret-shaped values from the input before logging.
        safe_input: dict = {}
        for key, value in tool_input.items():
            if isinstance(value, str) and contains_secret(value):
                safe_input[key] = "***REDACTED***"
            else:
                safe_input[key] = value
        summary = ", ".join(f"{k}={v}" for k, v in safe_input.items())
        self._entries.append(
            JournalEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                tool_name=tool_name,
                input_summary=summary[:200],
                success=success,
                error=error,
            )
        )
    def get_entries(self) -> list[JournalEntry]:
        return list(self._entries)
    def __len__(self) -> int:
        return len(self._entries)
