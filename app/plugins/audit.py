"""Plugin action audit — never stores secrets."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.secrets import redact_secrets
from app.plugins.models import PluginAuditEntry

_MAX = 400


class PluginAuditLog:
    def __init__(self) -> None:
        self._entries: list[PluginAuditEntry] = []

    def record(
        self, *, plugin_id: str, action: str, status: str,
        user_id: str | None = None, detail: str = ""
    ) -> None:
        self._entries.append(
            PluginAuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                plugin_id=plugin_id,
                user_id=user_id,
                action=action,
                status=status,
                detail=redact_secrets(detail)[:300],
            )
        )
        if len(self._entries) > _MAX:
            self._entries = self._entries[-_MAX:]

    def for_plugin(self, plugin_id: str, limit: int = 50) -> list[PluginAuditEntry]:
        items = [e for e in self._entries if e.plugin_id == plugin_id]
        return items[-limit:]

    def all(self, limit: int = 100) -> list[PluginAuditEntry]:
        return self._entries[-limit:]
