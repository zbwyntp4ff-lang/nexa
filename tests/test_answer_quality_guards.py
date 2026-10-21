"""Guards against echo replies, context loss markers, and fabricated source claims."""
from __future__ import annotations

import re

from app.core.nexa_core import _FAST_SYSTEM_PROMPT, _trim_history
from app.knowledge_core.feedback import FeedbackEvent, record_feedback, recent_feedback
from app.learning.eval import build_eval_cases, compute_feedback_stats
from app.models.chat import ChatMessage, ChatRole


_ECHO_RE = re.compile(
    r"^(вы\s+спросили|you\s+asked|ваш\s+вопрос|your\s+question)\s*[:：]",
    re.IGNORECASE,
)


def looks_like_question_echo(user_message: str, assistant_message: str) -> bool:
    """Heuristic used in tests — flags replies that only restate the question."""
    u = user_message.strip().lower()
    a = assistant_message.strip().lower()
    if not u or not a:
        return False
    if a == u or a.rstrip("?.!") == u.rstrip("?.!"):
        return True
    if _ECHO_RE.match(a) and u[:40] in a:
        return True
    # Whole reply is the question wrapped in quotes
    if a.strip("\"'«»") == u.strip("\"'«»"):
        return True
    return False


def test_echo_detector_catches_restatement():
    assert looks_like_question_echo("Что такое гравитация?", "Что такое гравитация?")
    assert looks_like_question_echo(
        "What is gravity?", "You asked: What is gravity?"
    )
    assert not looks_like_question_echo(
        "Что такое гравитация?",
        "Гравитация — притяжение масс; на Земле g ≈ 9.8 м/с².",
    )


def test_system_prompt_discourages_echo():
    assert "never echo" in _FAST_SYSTEM_PROMPT.lower()


def test_history_trim_keeps_recent_turns():
    history = [
        ChatMessage(role=ChatRole.USER, content=f"q{i}") for i in range(12)
    ]
    trimmed = _trim_history(history, limit=8)
    assert len(trimmed) == 8
    assert trimmed[0].content == "q4"
    assert trimmed[-1].content == "q11"


def test_feedback_ratings_and_eval_cases(tmp_path, monkeypatch):
    path = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(
        "app.knowledge_core.feedback._FEEDBACK_PATH", path
    )
    monkeypatch.setattr(
        "app.learning.eval.recent_feedback",
        lambda limit=200, user_id=None: recent_feedback(limit=limit, user_id=user_id),
    )
    record_feedback(
        FeedbackEvent(
            rating="factual_error",
            user_request="Столица Франции?",
            nexa_response="Берлин",
            note="wrong capital",
            user_id="u1",
        )
    )
    record_feedback(
        FeedbackEvent(
            rating="missing_sources",
            user_request="Latest news?",
            nexa_response="Something happened.",
            user_id="u1",
        )
    )
    record_feedback(
        FeedbackEvent(
            rating="useful",
            user_request="2+2?",
            nexa_response="4",
            user_id="u1",
        )
    )
    stats = compute_feedback_stats()
    assert stats.total == 3
    assert stats.by_rating.get("factual_error") == 1
    assert stats.positive_ratio is not None
    cases = build_eval_cases()
    assert any(c.rating == "factual_error" for c in cases)
