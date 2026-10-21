"""Task journal + eval report endpoints (no secrets)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.agent.journal import recent_journal
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.knowledge.eval_rag import evaluate_retrievers, write_rag_eval_report
from app.learning.eval_suite import run_eval_suite, write_eval_report

router = APIRouter(prefix="/api/v1", tags=["observability"])
_Auth = Annotated[UserRecord | None, Depends(require_user_when_enforced)]


class JournalResponse(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/journal", response_model=JournalResponse)
async def get_journal(
    limit: int = Query(default=100, ge=1, le=500),
    task_id: str | None = None,
    user: _Auth = None,
) -> JournalResponse:
    from app.config.settings import get_settings

    # Under multi-user enforce, require a task_id scope — global dump would
    # leak other users' tool timelines (even with scrubbed errors).
    if get_settings().tokens_enforce:
        if user is None or not task_id:
            return JournalResponse(events=[])
    return JournalResponse(events=recent_journal(limit=limit, task_id=task_id))


@router.post("/eval/rag")
async def run_rag_eval(_user: _Auth = None) -> dict[str, Any]:
    report = evaluate_retrievers()
    path = write_rag_eval_report(report)
    return {"report": report, "path": str(path)}


@router.post("/eval/suite")
async def run_model_eval(_user: _Auth = None) -> dict[str, Any]:
    report = await run_eval_suite()
    path = write_eval_report(report)
    return {"report": report, "path": str(path)}
