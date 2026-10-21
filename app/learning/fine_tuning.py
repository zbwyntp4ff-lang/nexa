"""Honest catalog of fine-tuning vs RAG vs prompt/context improvement.

This module documents capability — it does **not** launch training jobs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FineTuningCapability(BaseModel):
    category: str
    status: str
    providers: list[str] = Field(default_factory=list)
    notes: str


CAPABILITIES: list[FineTuningCapability] = [
    FineTuningCapability(
        category="parameter_update",
        status="not_enabled_in_product",
        providers=["openai (Jobs API)", "anthropic (limited/partner)", "gemini (tuning API)"],
        notes=(
            "OpenAI supports supervised fine-tuning via a separate Jobs API with "
            "JSONL datasets and paid training. Anthropic/Gemini have provider-specific "
            "tuning programs. NEXA does not auto-start these; dataset export and job "
            "launch would be explicit, confirmed, paid stages."
        ),
    ),
    FineTuningCapability(
        category="ollama_local_adapters",
        status="prep_only",
        providers=["ollama"],
        notes=(
            "Ollama can load Modelfiles / GGUF variants derived elsewhere (e.g. LoRA "
            "merged offline). NEXA can export feedback as eval/JSONL-style examples for "
            "offline training; it does not train weights inside the app."
        ),
    ),
    FineTuningCapability(
        category="rag",
        status="enabled",
        providers=["local_embeddings", "optional_future_remote_embeddings"],
        notes="Knowledge Base chunking + local hashing embeddings + keyword/semantic retrieval with citations.",
    ),
    FineTuningCapability(
        category="prompt_context",
        status="enabled_with_review",
        providers=["nexa_learning_loop"],
        notes=(
            "Personalization hints, approved memory injection, Knowledge Core packs, "
            "and reviewable improvement proposals. Feedback never silently rewrites "
            "system identity."
        ),
    ),
]


def capability_report() -> dict:
    return {
        "fine_tuning_automatic": False,
        "categories": [c.model_dump() for c in CAPABILITIES],
    }
