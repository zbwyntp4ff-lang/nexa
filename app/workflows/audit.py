"""In-memory workflow audit log. Secrets are redacted before they are stored."""
from __future__ import annotations
from app.core.secrets import contains_secret, redact_secrets
from app.workflows.models import AuditRecord, Workflow
def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    if contains_secret(value):
        return redact_secrets(value)
    return value
class WorkflowAuditLog:
    def record(
        self,
        workflow: Workflow,
        *,
        status: str,
        task_id: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        approval: str | None = None,
        error: str | None = None,
    ) -> AuditRecord:
        entry = AuditRecord(
            workflow_id=workflow.id,
            task_id=task_id,
            agent=agent,
            tool=tool,
            status=status,
            approval=approval,
            error=_clean(error),
        )
        workflow.audit.append(entry)
        return entry
