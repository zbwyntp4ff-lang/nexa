"""Learning & Memory — RAG, long-term memory hints, feedback eval.

This is **not** model fine-tuning. It stores allowed context, retrieves it,
and measures answer quality from user feedback.
"""
from app.learning.eval import FeedbackStats, compute_feedback_stats, run_eval_snapshot
from app.learning.improve import ImprovementProposal, propose_from_feedback
from app.learning.memory_context import build_memory_hint
from app.learning.settings import LearningSettings, get_learning_settings, save_learning_settings

__all__ = [
    "FeedbackStats",
    "ImprovementProposal",
    "LearningSettings",
    "build_memory_hint",
    "compute_feedback_stats",
    "get_learning_settings",
    "propose_from_feedback",
    "run_eval_snapshot",
    "save_learning_settings",
]
