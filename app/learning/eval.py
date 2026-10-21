"""Feedback-driven evaluation snapshots — measurable, not silent model edits."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.knowledge_core.feedback import FeedbackEvent, recent_feedback
from app.learning.settings import get_learning_settings, save_learning_settings


class FeedbackStats(BaseModel):
    total: int = 0
    by_rating: dict[str, int] = Field(default_factory=dict)
    with_notes: int = 0
    positive_ratio: float | None = None
    """Share of useful/up/correct among rated events; None if no ratings."""
    recurring_notes: list[str] = Field(default_factory=list)
    summary: str = ""


_POSITIVE = frozenset({"up", "useful", "correct"})
_NEGATIVE = frozenset(
    {
        "down",
        "not_useful",
        "incorrect",
        "incomplete",
        "outdated",
        "factual_error",
        "code_error",
        "missing_sources",
        "off_topic",
    }
)


def compute_feedback_stats(limit: int = 200) -> FeedbackStats:
    events = recent_feedback(limit=limit)
    counts: Counter[str] = Counter()
    with_notes = 0
    note_counts: Counter[str] = Counter()
    for event in events:
        counts[event.rating] += 1
        if event.note and event.note.strip():
            with_notes += 1
            note_counts[event.note.strip().lower()[:120]] += 1
    pos = sum(counts[r] for r in _POSITIVE if r in counts)
    neg = sum(counts[r] for r in _NEGATIVE if r in counts)
    rated = pos + neg
    ratio = (pos / rated) if rated else None
    recurring = [n for n, c in note_counts.most_common(5) if c >= 2]
    if not events:
        summary = "No feedback samples yet. Ratings create evaluation examples only — they do not retrain the model."
    elif ratio is None:
        summary = f"{len(events)} feedback samples stored (no positive/negative labels yet)."
    else:
        summary = (
            f"{len(events)} samples · positive_ratio={ratio:.0%} "
            f"(pos={pos}, neg={neg}). Feedback guides evaluation; it does not fine-tune weights."
        )
    return FeedbackStats(
        total=len(events),
        by_rating=dict(counts),
        with_notes=with_notes,
        positive_ratio=ratio,
        recurring_notes=recurring,
        summary=summary,
    )


def run_eval_snapshot() -> FeedbackStats:
    """Record a measurable snapshot into learning settings (no model mutation)."""
    stats = compute_feedback_stats()
    settings = get_learning_settings()
    settings.last_eval_at = datetime.now(timezone.utc).isoformat()
    settings.last_eval_summary = stats.summary
    save_learning_settings(settings)
    return stats


def build_eval_cases(limit: int = 50) -> list[FeedbackEvent]:
    """Export recent feedback as checkable examples (incorrect/incomplete preferred)."""
    events = recent_feedback(limit=limit)
    priority = [e for e in events if e.rating in _NEGATIVE]
    if len(priority) >= 5:
        return priority[-limit:]
    return events[-limit:]
