"""Delete an account and all related user-scoped data (backend enforcement).

Does not claim deletion from backups, CDN caches, or provider logs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.auth.store import AuthStore
from app.knowledge.knowledge_base import KnowledgeBase
from app.knowledge_core.feedback import delete_feedback_for_user
from app.memory.manager import MemoryManager
from app.profile.store import ProfileStore
from app.tokens.store import TokenStore


class AccountWipeReport(BaseModel):
    user_id: str
    memory_cleared: int = 0
    knowledge_documents_deleted: int = 0
    feedback_deleted: int = 0
    conversations_deleted: int = 0
    plugins_cleared: int = 0
    workflows_cleared: int = 0
    profile_deleted: bool = False
    tokens_cleared: bool = False
    sessions_revoked: int = 0
    user_deleted: bool = False
    details: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Server-side wipe completes for live stores; backups/replicas may retain data "
            "until their retention window expires (operator-controlled).",
            "External AI provider logs (if any) are outside NEXA's control.",
            "Browser local caches on other devices are not remotely wiped.",
        ]
    )


def wipe_user_account(
    *,
    user_id: str,
    auth_store: AuthStore,
    memory: MemoryManager,
    knowledge: KnowledgeBase,
    tokens: TokenStore | None = None,
    profiles: ProfileStore | None = None,
) -> AccountWipeReport:
    """Best-effort purge of user-owned data. Does not touch other users."""
    report = AccountWipeReport(user_id=user_id)
    report.sessions_revoked = auth_store.revoke_all_sessions_for_user(user_id)
    report.memory_cleared = memory.clear(user_id=user_id)
    report.knowledge_documents_deleted = knowledge.delete_user_data(user_id)
    report.feedback_deleted = delete_feedback_for_user(user_id)
    try:
        from app.conversations.store import get_conversation_store

        report.conversations_deleted = get_conversation_store().delete_all_for_user(user_id)
    except Exception as exc:  # noqa: BLE001
        report.details.append(f"conversations: {exc}")
    try:
        from app.plugins.manager import get_plugin_manager

        report.plugins_cleared = get_plugin_manager().delete_user_data(user_id)
    except Exception as exc:  # noqa: BLE001
        report.details.append(f"plugins: {exc}")
    try:
        from app.api.deps import get_workflow_engine

        report.workflows_cleared = get_workflow_engine().delete_user_workflows(user_id)
    except Exception as exc:  # noqa: BLE001
        report.details.append(f"workflows: {exc}")
    try:
        from app.attachments.manager import get_attachment_manager

        cleared = get_attachment_manager().delete_user(user_id)
        if cleared:
            report.details.append(f"attachments_cleared={cleared}")
    except Exception as exc:  # noqa: BLE001
        report.details.append(f"attachments: {exc}")
    if profiles is not None:
        try:
            profiles.delete(user_id)
            report.profile_deleted = True
        except Exception as exc:  # noqa: BLE001
            report.details.append(f"profile: {exc}")
    if tokens is not None:
        try:
            tokens.delete_user(user_id)
            report.tokens_cleared = True
        except Exception as exc:  # noqa: BLE001
            report.details.append(f"tokens: {exc}")
    report.user_deleted = auth_store.delete_user(user_id)
    return report
