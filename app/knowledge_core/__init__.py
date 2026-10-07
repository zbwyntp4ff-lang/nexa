"""NEXA Knowledge Core — structured behavior/knowledge packs over existing systems.

Does not replace Memory, Knowledge Base (RAG), web search, Omniverse, or tools.
It selects compact rule packs by intent and injects them into chat/agent context.
"""
from app.knowledge_core.composer import KnowledgeCoreComposer
from app.knowledge_core.feedback import FeedbackEvent, record_feedback
from app.knowledge_core.intents import detect_intents
from app.knowledge_core.models import ComposeResult, IntentKind, RulePack
from app.knowledge_core.store import load_packs, reload_packs

__all__ = [
    "ComposeResult",
    "FeedbackEvent",
    "IntentKind",
    "KnowledgeCoreComposer",
    "RulePack",
    "detect_intents",
    "load_packs",
    "record_feedback",
    "reload_packs",
]
