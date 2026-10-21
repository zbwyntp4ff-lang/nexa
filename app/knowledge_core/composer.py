"""Select and compose compact Knowledge Core fragments for a request."""
from __future__ import annotations

from app.knowledge_core.intents import detect_intents
from app.knowledge_core.models import ComposeResult, IntentKind, RulePack
from app.knowledge_core.store import load_packs

# Hard budget so Knowledge Core never recreates a giant prompt / TTFT tax.
_MAX_TOTAL_CHARS = 1400
_MAX_ALWAYS = 4
_MAX_INTENT = 2


class KnowledgeCoreComposer:
    """Intent-aware pack selector. Reuses existing Memory/RAG/Search elsewhere."""

    def __init__(self, packs: tuple[RulePack, ...] | None = None) -> None:
        # None → resolve at compose-time so reload_packs() takes effect without restart.
        self._packs = packs

    def compose(self, message: str, *, task: str | None = None) -> ComposeResult:
        packs = self._packs if self._packs is not None else load_packs()
        intents = detect_intents(message)
        if task:
            mapped = _task_to_intent(task)
            if mapped and mapped not in intents:
                intents = [mapped, *intents]

        always_packs, intent_packs = self._select(packs, intents, message)
        parts: list[str] = ["[NEXA Knowledge Core]"]
        used: list[str] = []
        remaining = _MAX_TOTAL_CHARS - len(parts[0])

        # Reserve room for at least one intent pack when present.
        intent_reserve = min(420, remaining // 3) if intent_packs else 0
        always_budget = max(200, remaining - intent_reserve)

        for pack in always_packs:
            block = self._clip(self._format_pack(pack), pack.max_chars)
            if len(block) + 1 > always_budget:
                block = block[: max(0, always_budget - 2)] + "…"
            if len(block) + 1 > remaining:
                break
            parts.append(block)
            used.append(pack.id)
            remaining -= len(block) + 1
            always_budget -= len(block) + 1

        for pack in intent_packs:
            block = self._clip(self._format_pack(pack), pack.max_chars)
            if len(block) + 1 > remaining:
                block = block[: max(0, remaining - 2)] + "…"
            if len(block) < 40:
                break
            parts.append(block)
            used.append(pack.id)
            remaining -= len(block) + 1

        text = "\n".join(parts) if used else ""
        return ComposeResult(
            intents=intents,
            pack_ids=used,
            text=text,
            char_count=len(text),
        )

    def _select(
        self,
        packs: tuple[RulePack, ...],
        intents: list[IntentKind],
        message: str,
    ) -> tuple[list[RulePack], list[RulePack]]:
        intent_ids = {i.value for i in intents}
        lowered = message.lower()
        always = sorted(
            [p for p in packs if p.always],
            key=lambda p: (p.priority, p.id),
        )[:_MAX_ALWAYS]

        scored: list[tuple[int, RulePack]] = []
        for pack in packs:
            if pack.always:
                continue
            score = 0
            if any(i in intent_ids for i in pack.intents):
                score += 100 + max(0, 60 - pack.priority)
            if any(trigger.lower() in lowered for trigger in pack.triggers):
                score += 80
            # Avoid pulling "general"-tagged packs for every greeting.
            if score > 0 and intent_ids == {"general"} and "general" in pack.intents:
                if not any(trigger.lower() in lowered for trigger in pack.triggers):
                    score = 0
            if score > 0:
                scored.append((score, pack))
        scored.sort(key=lambda item: (-item[0], item[1].priority, item[1].id))
        # Prefer unique pack ids (duplicate JSON files must not double-inject).
        intent_packs: list[RulePack] = []
        seen_ids = {p.id for p in always}
        for _, pack in scored:
            if pack.id in seen_ids:
                continue
            intent_packs.append(pack)
            seen_ids.add(pack.id)
            if len(intent_packs) >= _MAX_INTENT:
                break
        return always, intent_packs

    @staticmethod
    def _format_pack(pack: RulePack) -> str:
        lines = [f"## {pack.title}"]
        if pack.workflow:
            lines.append("Workflow: " + " → ".join(pack.workflow))
        for rule in pack.rules:
            lines.append(f"- {rule}")
        if pack.epistemic_labels:
            lines.append("Labels: " + ", ".join(pack.epistemic_labels))
        return "\n".join(lines)

    @staticmethod
    def _clip(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1] + "…"


def _task_to_intent(task: str) -> IntentKind | None:
    value = task.strip().lower()
    mapping = {
        "coding": IntentKind.CODE,
        "research": IntentKind.RESEARCH,
        "reasoning": IntentKind.RESEARCH,
        "simple": IntentKind.GENERAL,
        "local": IntentKind.GENERAL,
    }
    return mapping.get(value)
