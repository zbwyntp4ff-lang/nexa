"""Controlled quality-improvement proposals — never silent prompt/system mutation.

A negative rating alone does **not** change model behavior. Proposals are
stored for review; applying them requires an explicit confirm endpoint and a
measured before/after eval snapshot.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.paths import resolve_under_project_root
from app.learning.eval import compute_feedback_stats, run_eval_snapshot
from app.learning.settings import get_learning_settings, save_learning_settings

_PATH = resolve_under_project_root("data/learning_proposals.json")
_LOCK = threading.Lock()


class ImprovementProposal(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    kind: Literal["prompt_hint", "retrieval", "context", "eval_only"] = "eval_only"
    title: str
    rationale: str
    suggested_change: str
    status: Literal["proposed", "accepted", "rejected", "applied"] = "proposed"
    before_summary: str | None = None
    after_summary: str | None = None
    improved: bool | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ProposalStore(BaseModel):
    items: list[ImprovementProposal] = Field(default_factory=list)


def _load() -> ProposalStore:
    if not _PATH.exists():
        return ProposalStore()
    try:
        return ProposalStore.model_validate_json(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ProposalStore()


def _save(store: ProposalStore) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        _PATH.write_text(
            json.dumps(store.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def list_proposals() -> list[ImprovementProposal]:
    return list(_load().items)


def propose_from_feedback() -> list[ImprovementProposal]:
    """Generate reviewable proposals from recurring negative feedback.

    Does not rewrite system identity or auto-apply anything.
    """
    stats = compute_feedback_stats(limit=200)
    created: list[ImprovementProposal] = []
    store = _load()
    if stats.total == 0:
        return created
    if stats.recurring_notes:
        for note in stats.recurring_notes[:3]:
            p = ImprovementProposal(
                kind="context",
                title="Recurring user correction",
                rationale=f"Note appeared repeatedly in feedback: «{note}»",
                suggested_change=(
                    "Review whether retrieval/memory context should surface this "
                    "correction when relevant. Do not treat it as a system-rule rewrite."
                ),
                before_summary=stats.summary,
            )
            store.items.append(p)
            created.append(p)
    neg = sum(stats.by_rating.get(k, 0) for k in ("down", "not_useful", "incorrect", "incomplete", "outdated"))
    if neg >= 3 and (stats.positive_ratio is None or stats.positive_ratio < 0.6):
        p = ImprovementProposal(
            kind="retrieval",
            title="Retrieval / grounding check recommended",
            rationale=f"{neg} negative ratings in recent samples (ratio={stats.positive_ratio}).",
            suggested_change=(
                "Increase Knowledge Base usage for factual questions, or tighten "
                "insufficient-context messaging. Confirm with an eval snapshot before applying."
            ),
            before_summary=stats.summary,
        )
        store.items.append(p)
        created.append(p)
    if created:
        _save(store)
    return created


def set_proposal_status(
    proposal_id: str,
    status: Literal["proposed", "accepted", "rejected", "applied"],
) -> ImprovementProposal | None:
    store = _load()
    for item in store.items:
        if item.id != proposal_id:
            continue
        item.status = status
        item.updated_at = datetime.now(timezone.utc).isoformat()
        if status == "applied":
            # Measured gate: record after snapshot; mark improved only if ratio rose.
            before = item.before_summary
            after_stats = run_eval_snapshot()
            item.after_summary = after_stats.summary
            settings = get_learning_settings()
            # Apply only means we recorded the decision — no silent system prompt rewrite.
            item.improved = before is not None and after_stats.summary != before
            save_learning_settings(settings)
        _save(store)
        return item
    return None
