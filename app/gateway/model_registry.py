"""ModelRegistry — catalog plus live availability.
Availability is computed from server configuration (API key present) and, for
Ollama, from the models the local server reports. API keys are never copied
onto a card.
"""
from __future__ import annotations
from app.gateway.models import ModelCard
# Allow `/` for OpenRouter-style ids (e.g. meta-llama/llama-3.2-3b-instruct:free).
# Reject path traversal (`..`) and absolute/relative dots sequences.
_SAFE_MODEL_ID = __import__("re").compile(r"^[A-Za-z0-9_.:@/-]{1,128}$")
def is_safe_model_id(model_id: str) -> bool:
    if ".." in model_id or model_id.startswith("/") or model_id.startswith("./"):
        return False
    return bool(_SAFE_MODEL_ID.match(model_id))
def _ollama_matches(installed: str, requested: str) -> bool:
    return installed == requested or installed.split(":", 1)[0] == requested
def _vision_from_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("llava", "vision", "moondream", "bakllava"))


def _vision_only_from_name(name: str) -> bool:
    """Caption/vision models that do not reliably answer text chat (e.g. moondream)."""
    lowered = name.lower()
    return any(token in lowered for token in ("moondream",))


class ModelRegistry:
    def __init__(self, static_cards: list[ModelCard]) -> None:
        self._static = list(static_cards)
        self._ollama_models: list[str] = []
        self._ollama_reachable: bool | None = None
    def set_ollama(self, names: list[str], reachable: bool) -> None:
        self._ollama_models = list(names)
        self._ollama_reachable = reachable
    def cards(
        self,
        *,
        openai_configured: bool,
        anthropic_configured: bool,
        gemini_configured: bool = False,
        openrouter_configured: bool = False,
        hexa_configured: bool = False,
        include_mock: bool = True,
    ) -> list[ModelCard]:
        configured = {
            "openai": openai_configured,
            "anthropic": anthropic_configured,
            "gemini": gemini_configured,
            "openrouter": openrouter_configured,
            "hexa": hexa_configured,
        }
        result: list[ModelCard] = []
        for card in self._static:
            if card.provider == "mock" and not include_mock:
                continue
            copy = card.model_copy()
            if card.provider in configured:
                ok = configured[card.provider]
                copy.availability = "available" if ok else "unavailable"
                copy.availability_reason = None if ok else "missing_api_key"
            elif card.provider == "mock":
                copy.availability = "available"
                copy.availability_reason = None
            result.append(copy)
        result.extend(self._ollama_cards())
        return result
    def _ollama_cards(self) -> list[ModelCard]:
        if self._ollama_reachable is False:
            return [
                ModelCard(
                    provider="ollama",
                    model_id="llama3",
                    display_name="Ollama",
                    capabilities=["chat", "local", "private"],
                    supports_streaming=True,
                    supports_tools=True,
                    availability="unavailable",
                    availability_reason="provider_unavailable",
                )
            ]
        cards: list[ModelCard] = []
        for name in self._ollama_models:
            vision = _vision_from_name(name)
            vision_only = _vision_only_from_name(name)
            if vision_only:
                # Do not advertise "chat" — these models hang or emit garbage on text-only prompts.
                capabilities = ["vision", "local", "private"]
            else:
                capabilities = ["chat", "local", "private", "tools"]
                if vision:
                    capabilities.append("vision")
            cards.append(
                ModelCard(
                    provider="ollama",
                    model_id=name,
                    display_name=name,
                    capabilities=capabilities,
                    context_window=None,
                    supports_vision=vision,
                    supports_tools=not vision_only,
                    supports_streaming=True,
                    availability="available",
                    availability_reason=None,
                )
            )
        return cards
    def find(self, model_id: str, provider: str | None = None) -> ModelCard | None:
        cards = self.cards(
            openai_configured=True,
            anthropic_configured=True,
            gemini_configured=True,
            openrouter_configured=True,
        )
        # Re-find against the last published snapshot is wrong for availability.
        # Callers should search the list they already computed.
        return _find_in(cards, model_id, provider)
    def resolve_installed_id(self, model_id: str) -> str:
        """Map ``llama3`` to ``llama3:latest`` when that is what Ollama reports."""
        for name in self._ollama_models:
            if _ollama_matches(name, model_id):
                return name
        return model_id
def _find_in(cards: list[ModelCard], model_id: str, provider: str | None) -> ModelCard | None:
    for card in cards:
        if provider and card.provider != provider:
            continue
        if card.model_id == model_id:
            return card
    if provider in (None, "ollama", "local"):
        for card in cards:
            if card.provider == "ollama" and _ollama_matches(card.model_id, model_id):
                return card
    return None
def find_card(cards: list[ModelCard], model_id: str, provider: str | None = None) -> ModelCard | None:
    return _find_in(cards, model_id, provider)
