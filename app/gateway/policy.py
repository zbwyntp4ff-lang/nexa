"""Model selection policy.
Maps a task kind to a configured route (which capability to look for, and in
which order to try configured model ids). This is not a rating and it does
not claim that one model is objectively better than another.
"""
from __future__ import annotations
from app.gateway.models import ModelCard, TaskKind
# Capability a task kind asks for. Models tagged with it are eligible.
_CAPABILITY = {
    TaskKind.SIMPLE: "simple",
    TaskKind.REASONING: "reasoning",
    TaskKind.CODING: "coding",
    TaskKind.RESEARCH: "tools",
    TaskKind.LOCAL: "local",
}
# Configured try-order for cloud models. Ollama is added separately.
_ROUTE: dict[TaskKind, tuple[str, ...]] = {
    TaskKind.SIMPLE: ("gpt-4.1-mini", "claude-3-5-haiku-latest", "gpt-4o-mini"),
    TaskKind.REASONING: ("gpt-4o", "claude-opus-4-20250514"),
    TaskKind.CODING: ("gpt-4o-mini", "claude-sonnet-4-20250514", "gpt-4o"),
    TaskKind.RESEARCH: ("gpt-4o", "claude-opus-4-20250514", "gpt-4o-mini", "claude-sonnet-4-20250514"),
    TaskKind.LOCAL: (),
}
_LOCAL_WORDS = (
    "local only",
    "keep this local",
    "private task",
    "offline",
    "локально",
    "приватн",
    "не отправляй",
    "офлайн",
)
_RESEARCH_WORDS = (
    "search the web",
    "web research",
    "look up",
    "найди в интернете",
    "поиск в интернете",
    "исследуй",
)
_CODING_WORDS = (
    "write code",
    "fix the bug",
    "refactor",
    "function",
    "напиши код",
    "исправь код",
    "функци",
)
_REASONING_WORDS = (
    "step by step",
    "reason about",
    "prove that",
    "analyze why",
    "рассуж",
    "докаж",
    "проанализ",
)
def infer_task_kind(text: str) -> TaskKind:
    """Pick a task kind from the user's text. Defaults to simple."""
    lowered = text.lower()
    if any(word in lowered for word in _LOCAL_WORDS):
        return TaskKind.LOCAL
    if any(word in lowered for word in _RESEARCH_WORDS):
        return TaskKind.RESEARCH
    if any(word in lowered for word in _CODING_WORDS):
        return TaskKind.CODING
    if any(word in lowered for word in _REASONING_WORDS):
        return TaskKind.REASONING
    return TaskKind.SIMPLE
def parse_task_kind(value: str | None, text: str) -> TaskKind:
    if value:
        try:
            return TaskKind(value.strip().lower())
        except ValueError:
            pass
    return infer_task_kind(text)
class ModelSelectionPolicy:
    """Chooses an ordered list of available models for a task kind."""
    def candidates(
        self,
        kind: TaskKind,
        cards: list[ModelCard],
        *,
        allow_cloud_for_local: bool,
    ) -> list[ModelCard]:
        available = [card for card in cards if card.availability == "available"]
        local = [card for card in available if card.provider in ("ollama", "local")]
        cloud = [card for card in available if card.provider not in ("ollama", "local", "mock")]
        if kind == TaskKind.LOCAL:
            if local:
                return _prefer_smaller_local(local)
            if allow_cloud_for_local:
                return cloud
            return []
        by_id = {card.model_id: card for card in available}
        ordered: list[ModelCard] = []
        for model_id in _ROUTE[kind]:
            card = by_id.get(model_id)
            if card is not None and card not in ordered:
                ordered.append(card)
        needed = _CAPABILITY[kind]
        for card in available:
            if card.provider == "mock":
                continue
            if card not in ordered and needed in card.capabilities:
                ordered.append(card)
        if kind == TaskKind.SIMPLE:
            # Fast path for ordinary chat: local small models before heavy/cloud.
            local_chat = [c for c in local if "chat" in c.capabilities]
            ordered = _dedupe_cards([*_prefer_smaller_local(local_chat), *ordered, *cloud])
        if not ordered:
            # Whatever is actually configured and reachable, cloud first then local.
            ordered = [*cloud, *local]
            if not ordered:
                ordered = [card for card in available if card.provider == "mock"]
        return ordered


def _param_score(model_id: str) -> float:
    import re

    match = re.search(r"(\d+(?:\.\d+)?)\s*[bB]\b", model_id)
    return float(match.group(1)) if match else 7.0


def _prefer_smaller_local(cards: list[ModelCard]) -> list[ModelCard]:
    return sorted(cards, key=lambda c: (_param_score(c.model_id), c.model_id))


def _dedupe_cards(cards: list[ModelCard]) -> list[ModelCard]:
    seen: set[tuple[str, str]] = set()
    out: list[ModelCard] = []
    for card in cards:
        key = (card.provider, card.model_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
    return out
