"""Knowledge Core API — pack listing + learning-loop feedback.

Does not replace Knowledge Base (RAG) or Memory; it exposes the structured
behavior/knowledge packs and stores evaluation feedback for later improvement.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.knowledge_core.composer import KnowledgeCoreComposer
from app.knowledge_core.feedback import FeedbackEvent, recent_feedback, record_feedback
from app.knowledge_core.store import load_packs, reload_packs

router = APIRouter(prefix="/api/v1/knowledge-core", tags=["knowledge-core"])


class PackSummary(BaseModel):
    id: str
    title: str
    always: bool
    intents: list[str]
    priority: int
    rule_count: int


class ComposePreviewRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    task: str | None = None


class ComposePreviewResponse(BaseModel):
    intents: list[str]
    pack_ids: list[str]
    text: str
    char_count: int


@router.get("/packs", response_model=list[PackSummary])
async def list_packs() -> list[PackSummary]:
    return [
        PackSummary(
            id=pack.id,
            title=pack.title,
            always=pack.always,
            intents=pack.intents,
            priority=pack.priority,
            rule_count=len(pack.rules),
        )
        for pack in load_packs()
    ]


@router.post("/reload", response_model=list[PackSummary])
async def reload() -> list[PackSummary]:
    packs = reload_packs()
    return [
        PackSummary(
            id=pack.id,
            title=pack.title,
            always=pack.always,
            intents=pack.intents,
            priority=pack.priority,
            rule_count=len(pack.rules),
        )
        for pack in packs
    ]


@router.post("/compose", response_model=ComposePreviewResponse)
async def compose_preview(body: ComposePreviewRequest) -> ComposePreviewResponse:
    result = KnowledgeCoreComposer().compose(body.message, task=body.task)
    return ComposePreviewResponse(
        intents=[i.value for i in result.intents],
        pack_ids=result.pack_ids,
        text=result.text,
        char_count=result.char_count,
    )


@router.post("/feedback", response_model=FeedbackEvent)
async def submit_feedback(body: FeedbackEvent) -> FeedbackEvent:
    """Store an evaluation example. Does not auto-train the model."""
    return record_feedback(body)


@router.get("/feedback", response_model=list[FeedbackEvent])
async def list_feedback(limit: int = 50) -> list[FeedbackEvent]:
    return recent_feedback(limit=min(max(limit, 1), 200))
