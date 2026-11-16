"""Learning & Memory settings, eval snapshots, and improvement proposals."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, get_memory_manager_dep, get_settings
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import Settings
from app.knowledge.knowledge_base import KnowledgeBase, get_knowledge_base
from app.learning.eval import FeedbackStats, compute_feedback_stats, run_eval_snapshot
from app.learning.fine_tuning import capability_report
from app.learning.improve import (
    ImprovementProposal,
    list_proposals,
    propose_from_feedback,
    set_proposal_status,
)
from app.learning.settings import LearningSettings, get_learning_settings, save_learning_settings
from app.memory.manager import MemoryManager

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])


def require_learning_admin(
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Protect shared learning controls and global improvement proposals."""
    if user is None:
        if settings.tokens_enforce:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return
    if not auth.is_owner(user):
        raise HTTPException(status_code=403, detail="Only the NEXA owner can manage global learning controls.")


def _knowledge_base() -> KnowledgeBase:
    return get_knowledge_base()


def _default_fine_tuning() -> dict:
    return {
        "available_in_product": False,
        "note": (
            "NEXA does not run automatic fine-tuning. RAG and memory store/retrieve "
            "context; eval proposals require confirmation. Cloud fine-tuning APIs "
            "(OpenAI/etc.) are not auto-started."
        ),
        "categories": {
            "parameter_update": "not_enabled",
            "rag": "enabled_opt_in",
            "prompt_context": "enabled_with_review",
        },
        "report": capability_report(),
    }


class LearningStatusResponse(BaseModel):
    settings: LearningSettings
    memory_enabled: bool
    memory_item_count: int
    knowledge_document_count: int
    knowledge_chunk_hint: str
    feedback_stats: FeedbackStats
    last_index_at: str | None
    last_eval_at: str | None
    last_eval_summary: str | None
    mechanisms: list[str] = Field(
        default_factory=lambda: [
            "long_term_memory_injection",
            "knowledge_base_rag",
            "feedback_eval_snapshots",
            "improvement_proposals_review",
        ]
    )
    fine_tuning: dict = Field(default_factory=_default_fine_tuning)
    requires_confirmation: list[str] = Field(
        default_factory=lambda: [
            "apply_improvement_proposal",
            "clear_all_memory",
            "delete_knowledge_document",
            "paid_cloud_document_send",
            "any_fine_tuning_job",
        ]
    )


class LearningSettingsUpdate(BaseModel):
    memory_enabled: bool | None = None
    feedback_enabled: bool | None = None
    auto_knowledge_base: bool | None = None
    allow_cloud_on_documents: bool | None = None


class ProposalStatusUpdate(BaseModel):
    status: Literal["proposed", "accepted", "rejected", "applied"]


@router.get("/status", response_model=LearningStatusResponse)
async def learning_status(
    memory: MemoryManager = Depends(get_memory_manager_dep),
    kb: KnowledgeBase = Depends(_knowledge_base),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> LearningStatusResponse:
    settings = get_learning_settings()
    scoped = user.id if user is not None else None
    mem_count = len(memory.search(query="", user_id=scoped, limit=1000))
    docs = kb.list_documents()
    # Touch last_index from newest document if settings blank
    last_index = settings.last_index_at
    if docs and not last_index:
        newest = max(docs, key=lambda d: d.created_at)
        last_index = (
            newest.created_at.isoformat()
            if hasattr(newest.created_at, "isoformat")
            else str(newest.created_at)
        )
    stats = compute_feedback_stats()
    return LearningStatusResponse(
        settings=settings,
        memory_enabled=settings.memory_enabled,
        memory_item_count=mem_count,
        knowledge_document_count=len(docs),
        knowledge_chunk_hint="Indexed via Knowledge Base vector/keyword store",
        feedback_stats=stats,
        last_index_at=last_index,
        last_eval_at=settings.last_eval_at,
        last_eval_summary=settings.last_eval_summary,
    )


@router.get("/settings", response_model=LearningSettings)
async def get_settings_route(
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> LearningSettings:
    return get_learning_settings()


@router.put("/settings", response_model=LearningSettings, dependencies=[Depends(require_learning_admin)])
async def put_settings(
    body: LearningSettingsUpdate,
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> LearningSettings:
    current = get_learning_settings()
    data = current.model_dump()
    for key, value in body.model_dump(exclude_none=True).items():
        data[key] = value
    return save_learning_settings(LearningSettings.model_validate(data))


@router.post("/eval/run", response_model=FeedbackStats, dependencies=[Depends(require_learning_admin)])
async def eval_run(
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> FeedbackStats:
    return run_eval_snapshot()


@router.get("/proposals", response_model=list[ImprovementProposal], dependencies=[Depends(require_learning_admin)])
async def proposals_list(
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> list[ImprovementProposal]:
    return list_proposals()


@router.post("/proposals/generate", response_model=list[ImprovementProposal], dependencies=[Depends(require_learning_admin)])
async def proposals_generate(
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> list[ImprovementProposal]:
    return propose_from_feedback()


@router.post("/proposals/{proposal_id}/status", response_model=ImprovementProposal, dependencies=[Depends(require_learning_admin)])
async def proposals_status(
    proposal_id: str,
    body: ProposalStatusUpdate,
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> ImprovementProposal:
    item = set_proposal_status(proposal_id, body.status)
    if item is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return item


@router.post("/mark-indexed", response_model=LearningSettings, dependencies=[Depends(require_learning_admin)])
async def mark_indexed(
    _user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> LearningSettings:
    settings = get_learning_settings()
    settings.last_index_at = datetime.now(timezone.utc).isoformat()
    return save_learning_settings(settings)
