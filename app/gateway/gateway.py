"""ModelGateway.
NEXA, the agent, and the orchestrator talk only to this object. It picks a
model, opens the matching real provider, and normalizes errors. It never
puts API keys into prompts, logs, or return values.
"""
from __future__ import annotations
import base64
import json
import re
import time
from collections.abc import AsyncIterator
from app.config.settings import Settings
from app.core.logging_config import get_logger
from app.core.paths import resolve_under_project_root
from app.core.secrets import contains_secret
from app.gateway.catalog import static_catalog
from app.gateway.errors import (
    AUTHENTICATION_ERROR,
    MODEL_UNAVAILABLE,
    GatewayError,
    missing_api_key_error,
    normalize_provider_error,
)
from app.gateway.model_registry import ModelRegistry, find_card, is_safe_model_id
from app.gateway.models import GatewayResult, ModelCard, Selection, StreamEvent, TaskKind
from app.gateway.policy import ModelSelectionPolicy, parse_task_kind
from app.gateway.provider_registry import ProviderRegistry
from app.models.chat import ChatMessage, ChatRole, ImageAttachment
from app.models.errors import ModelCapabilityError, ProviderConfigurationError, UnknownProviderError
from app.providers.base import AIProvider
logger = get_logger("nexa.gateway")
# Tags listing is only for availability UI — do not hit Ollama on every chat token.
_OLLAMA_REFRESH_SECONDS = 60.0
# The user's provider/model choice (and fallback preference) is a UI
# setting, not a secret, so it is persisted here as plain JSON. Without
# this, the selection would silently reset to the .env default every time
# the desktop app (and its backend process) restarts.
_SELECTION_STORE_PATH = resolve_under_project_root("data/model_selection.json")
def _load_persisted_selection() -> Selection | None:
    """Return the previously saved selection, or ``None`` if there isn't one."""
    try:
        if not _SELECTION_STORE_PATH.exists():
            return None
        raw = json.loads(_SELECTION_STORE_PATH.read_text(encoding="utf-8"))
        return Selection(
            mode=raw.get("mode", "auto"),
            provider=raw.get("provider"),
            model_id=raw.get("model_id"),
            allow_fallback=bool(raw.get("allow_fallback", False)),
        )
    except (OSError, ValueError, TypeError):
        logger.warning("Could not read persisted model selection; using defaults.")
        return None
def _save_persisted_selection(selection: Selection) -> None:
    """Best-effort persist of ``selection`` so it survives app restarts."""
    try:
        _SELECTION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SELECTION_STORE_PATH.write_text(
            json.dumps(
                {
                    "mode": selection.mode,
                    "provider": selection.provider,
                    "model_id": selection.model_id,
                    "allow_fallback": selection.allow_fallback,
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Could not persist model selection to disk.")
def build_provider_registry(settings: Settings) -> ProviderRegistry:
    """Register OpenAI, Anthropic, Gemini, OpenRouter, Ollama, and mock providers."""
    registry = ProviderRegistry()
    timeout = settings.request_timeout_seconds
    def openai_factory(model_id: str) -> AIProvider:
        from app.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=model_id,
            timeout_seconds=timeout,
        )
    def anthropic_factory(model_id: str) -> AIProvider:
        from app.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=model_id,
            timeout_seconds=timeout,
        )
    def gemini_factory(model_id: str) -> AIProvider:
        from app.providers.gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=settings.resolved_gemini_api_key,
            model=model_id,
            timeout_seconds=timeout,
        )
    def openrouter_factory(model_id: str) -> AIProvider:
        from app.providers.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            model=model_id,
            timeout_seconds=timeout,
            base_url=settings.openrouter_base_url,
        )
    def ollama_factory(model_id: str) -> AIProvider:
        from app.providers.ollama_provider import OllamaProvider
        return OllamaProvider(
            base_url=settings.local_model_url,
            model=model_id,
            timeout_seconds=timeout,
        )
    def local_factory(model_id: str) -> AIProvider:
        from app.providers.local_provider import LocalProvider
        return LocalProvider(
            base_url=settings.local_model_url,
            model=model_id,
            timeout_seconds=timeout,
        )
    def hexa_factory(model_id: str) -> AIProvider:
        from app.providers.hexa_provider import Hexa45Provider
        return Hexa45Provider(
            base_url=settings.hexa_model_url,
            model=model_id or settings.hexa_model_name,
            timeout_seconds=timeout,
        )
    def mock_factory(model_id: str) -> AIProvider:
        from app.providers.mock import MockProvider
        return MockProvider(model_name=model_id or "nexa-mock-1")
    registry.register("openai", openai_factory)
    registry.register("anthropic", anthropic_factory)
    registry.register("gemini", gemini_factory)
    registry.register("openrouter", openrouter_factory)
    registry.register("ollama", ollama_factory)
    registry.register("local", local_factory)
    registry.register("mock", mock_factory)
    registry.register("hexa", hexa_factory)
    return registry
def initial_selection(settings: Settings) -> Selection:
    raw = (settings.model_selection or "").strip().lower()
    if raw == "auto":
        return Selection(mode="auto", allow_fallback=settings.allow_model_fallback)
    provider = settings.ai_provider
    if provider == "local":
        provider = "ollama"
    model_id = {
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "gemini": settings.gemini_model,
        "openrouter": settings.openrouter_model,
        "ollama": settings.local_model_name,
        "hexa": settings.hexa_model_name,
        "mock": "nexa-mock-1",
    }.get(provider, settings.local_model_name)
    return Selection(
        mode="manual",
        provider=provider,
        model_id=model_id,
        allow_fallback=settings.allow_model_fallback,
    )
class ModelGateway:
    def __init__(
        self,
        providers: ProviderRegistry,
        models: ModelRegistry,
        settings: Settings,
        policy: ModelSelectionPolicy | None = None,
        selection: Selection | None = None,
    ) -> None:
        self._providers = providers
        self._models = models
        self._settings = settings
        self._policy = policy or ModelSelectionPolicy()
        # Priority: an explicitly passed-in selection (tests) > a selection
        # the user previously saved via the UI (survives app restarts) >
        # the .env-derived default.
        self._selection = selection or _load_persisted_selection() or initial_selection(settings)
        self._last: GatewayResult | None = None
        self._ollama_checked_at = 0.0
    @property
    def selection(self) -> Selection:
        return self._selection
    @property
    def last_result(self) -> GatewayResult | None:
        return self._last

    def _raise_if_kill_switch(self) -> None:
        if bool(getattr(self._settings, "ai_kill_switch", False)):
            raise GatewayError(
                MODEL_UNAVAILABLE,
                "AI is temporarily disabled by the operator. Please try again later.",
            )

    def set_selection(self, provider: str, model: str, allow_fallback: bool) -> Selection:
        provider_name = provider.strip().lower()
        model_id = model.strip()
        if provider_name == "auto" or model_id.lower() == "auto":
            self._selection = Selection(mode="auto", allow_fallback=allow_fallback)
            logger.info("gateway selection mode=auto allow_fallback=%s", allow_fallback)
            _save_persisted_selection(self._selection)
            return self._selection
        if provider_name == "local":
            provider_name = "ollama"
        if provider_name not in self._providers.names():
            raise UnknownProviderError(provider_name, available=self._providers.names())
        if not is_safe_model_id(model_id) or contains_secret(model_id):
            raise GatewayError(MODEL_UNAVAILABLE, "Invalid model id.", provider=provider_name)
        self._selection = Selection(
            mode="manual",
            provider=provider_name,
            model_id=model_id,
            allow_fallback=allow_fallback,
        )
        logger.info(
            "gateway selection mode=manual provider=%s model=%s allow_fallback=%s",
            provider_name,
            model_id,
            allow_fallback,
        )
        _save_persisted_selection(self._selection)
        return self._selection
    async def refresh_ollama(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._ollama_checked_at) < _OLLAMA_REFRESH_SECONDS:
            return
        self._ollama_checked_at = now
        from app.providers.ollama_provider import fetch_installed_models
        try:
            names = await fetch_installed_models(self._settings.local_model_url)
        except Exception:  # noqa: BLE001 - availability only, never log the URL userinfo
            self._models.set_ollama([], reachable=False)
            logger.info("gateway ollama unreachable")
            return
        self._models.set_ollama(names, reachable=True)
        logger.info("gateway ollama models=%d", len(names))
    def _allow_mock_cards(self) -> bool:
        """Mock is only for explicit AI_PROVIDER=mock / tests — never a silent fallback."""
        return (self._settings.ai_provider or "").strip().lower() == "mock"

    def _cards(self, *, include_mock: bool | None = None) -> list[ModelCard]:
        if include_mock is None:
            include_mock = self._allow_mock_cards()
        return self._models.cards(
            openai_configured=bool(self._settings.openai_api_key),
            anthropic_configured=bool(self._settings.anthropic_api_key),
            gemini_configured=bool(self._settings.resolved_gemini_api_key),
            openrouter_configured=bool(self._settings.openrouter_api_key),
            hexa_configured=bool(self._settings.hexa_model_url),
            include_mock=include_mock,
        )
    async def list_models(self, *, include_mock: bool = False) -> list[ModelCard]:
        await self.refresh_ollama()
        return self._cards(include_mock=include_mock)
    def _custom_card(self, provider: str, model_id: str) -> ModelCard:
        configured = {
            "openai": bool(self._settings.openai_api_key),
            "anthropic": bool(self._settings.anthropic_api_key),
            "gemini": bool(self._settings.resolved_gemini_api_key),
            "openrouter": bool(self._settings.openrouter_api_key),
            "hexa": bool(self._settings.hexa_model_url),
            "ollama": self._models._ollama_reachable is not False,
            "local": self._models._ollama_reachable is not False,
            "mock": self._allow_mock_cards(),
        }.get(provider, False)
        reason = None
        availability = "available" if configured else "unavailable"
        if provider in ("openai", "anthropic", "gemini", "openrouter") and not configured:
            reason = "missing_api_key"
        if provider == "hexa" and not configured:
            reason = "missing_model_endpoint"
        if provider in ("ollama", "local") and self._models._ollama_reachable is False:
            reason = "provider_unavailable"
            availability = "unavailable"
        resolved = model_id
        if provider in ("ollama", "local"):
            resolved = self._models.resolve_installed_id(model_id)
            if self._models._ollama_models and resolved == model_id:
                if not any(
                    name == model_id or name.split(":", 1)[0] == model_id
                    for name in self._models._ollama_models
                ):
                    availability = "unavailable"
                    reason = "not_installed"
        return ModelCard(
            provider="ollama" if provider == "local" else provider,
            model_id=resolved,
            display_name=resolved,
            capabilities=["chat"],
            supports_streaming=True,
            availability=availability,
            availability_reason=reason,
        )
    def _card(self, provider: str, model_id: str, cards: list[ModelCard]) -> ModelCard:
        found = find_card(cards, model_id, provider)
        if found is not None:
            if found.provider == "ollama":
                resolved = self._models.resolve_installed_id(found.model_id)
                if resolved != found.model_id:
                    return found.model_copy(update={"model_id": resolved})
            return found
        return self._custom_card(provider, model_id)
    def _attempts(
        self,
        cards: list[ModelCard],
        *,
        model: str | None,
        kind: TaskKind,
        allow_fallback: bool | None,
    ) -> list[ModelCard]:
        selection = self._selection
        fallback = selection.allow_fallback if allow_fallback is None else allow_fallback
        manual_model = model.strip() if model else None
        if manual_model and manual_model.lower() != "auto":
            provider = self._provider_for_model(manual_model, cards) or selection.provider
            if provider is None:
                raise GatewayError(MODEL_UNAVAILABLE, "Unknown model.", model=manual_model)
            primary = self._card(provider, manual_model, cards)
            attempts = [primary]
            if fallback:
                attempts.extend(self._fallback_after(primary, kind, cards, fallback))
            return _dedupe(attempts)
        if selection.mode == "manual" and selection.provider and selection.model_id and (not manual_model):
            primary = self._card(selection.provider, selection.model_id, cards)
            attempts = [primary]
            if fallback:
                attempts.extend(self._fallback_after(primary, kind, cards, fallback))
            return _dedupe(attempts)
        # Auto: policy order. Transient fallback is part of Auto.
        allow_cloud = fallback or selection.mode == "auto"
        ordered = self._policy.candidates(kind, cards, allow_cloud_for_local=fallback)
        if selection.mode == "auto" or (manual_model and manual_model.lower() == "auto"):
            if not fallback:
                # Auto still tries the next model on a transient error, but a
                # private task is not sent to a cloud provider unless fallback
                # was explicitly allowed. That exception is handled in policy.
                pass
            return ordered
        return ordered
    def _provider_for_model(self, model_id: str, cards: list[ModelCard]) -> str | None:
        found = find_card(cards, model_id, None)
        return found.provider if found else None
    def _fallback_after(
        self,
        primary: ModelCard,
        kind: TaskKind,
        cards: list[ModelCard],
        allow_fallback: bool,
    ) -> list[ModelCard]:
        ordered = self._policy.candidates(kind, cards, allow_cloud_for_local=allow_fallback)
        return [card for card in ordered if not _same(card, primary)]
    def _unavailable_message(self, cards: list[ModelCard]) -> str:
        reasons: list[str] = []
        if not self._settings.openai_api_key:
            reasons.append("OpenAI: API key is not configured")
        if not self._settings.anthropic_api_key:
            reasons.append("Anthropic: API key is not configured")
        ollama = [card for card in cards if card.provider == "ollama"]
        if not any(card.availability == "available" for card in ollama):
            reason = ollama[0].availability_reason if ollama else "not_installed"
            if reason == "provider_unavailable":
                reasons.append("Ollama: server is not reachable")
            else:
                reasons.append("Ollama: no installed local model")
        if not reasons:
            return "No model is available for this task."
        return "No model is available for this task. " + "; ".join(reasons) + "."
    def _open(self, card: ModelCard) -> AIProvider:
        if card.provider == "hexa" and not self._settings.hexa_model_url:
            raise GatewayError(
                MODEL_UNAVAILABLE,
                "HEXA inference endpoint is not configured. Set HEXA_MODEL_URL in the backend environment.",
                provider="hexa",
                model=card.model_id,
            )
        if card.availability_reason == "missing_api_key" or (
            card.provider in ("openai", "anthropic", "gemini", "openrouter")
            and card.availability != "available"
            and not _key_for(self._settings, card.provider)
        ):
            raise missing_api_key_error(card.provider)
        try:
            return self._providers.create(card.provider, card.model_id)
        except ProviderConfigurationError as exc:
            if card.provider == "hexa":
                raise GatewayError(
                    MODEL_UNAVAILABLE,
                    "HEXA inference endpoint is not configured. Set HEXA_MODEL_URL in the backend environment.",
                    provider="hexa",
                    model=card.model_id,
                ) from exc
            raise missing_api_key_error(card.provider) from exc
    def _is_manual_request(self, model: str | None) -> bool:
        manual_model = model.strip() if model else None
        if manual_model and manual_model.lower() != "auto":
            return True
        return self._selection.mode == "manual"
    def _require_vision(
        self, attempts: list[ModelCard], cards: list[ModelCard], *, manual: bool
    ) -> list[ModelCard]:
        """Filter ``attempts`` down to vision-capable models, or raise clearly.
        Manual selections never silently swap to a different model for
        capability reasons - only the explicitly chosen model is considered,
        and a mismatch raises immediately with suggestions.
        """
        if manual:
            primary = attempts[0]
            if primary.supports_vision:
                return [primary]
            raise ModelCapabilityError(
                f"{primary.display_name} does not support image input. "
                + self._vision_suggestion(cards)
            )
        capable = [card for card in attempts if card.supports_vision]
        if capable:
            return capable
        # Auto: the narrow task-kind route had no vision-capable model, but
        # a vision capability is required by this request - widen the
        # search to any currently available vision-capable model rather
        # than failing outright, per the "consider task capabilities" rule.
        broadened = [card for card in cards if card.supports_vision and card.availability == "available"]
        if broadened:
            return broadened
        raise ModelCapabilityError(
            "No currently available model supports image input. " + self._vision_suggestion(cards)
        )
    @staticmethod
    def _vision_suggestion(cards: list[ModelCard]) -> str:
        names = [card.display_name for card in cards if card.supports_vision and card.availability == "available"]
        if names:
            return f"Compatible models available: {', '.join(names)}."
        return "No vision-capable model is currently available."

    def _require_chat(
        self, attempts: list[ModelCard], cards: list[ModelCard], *, manual: bool
    ) -> list[ModelCard]:
        """Drop vision-only caption models from text chat (they hang / emit garbage)."""

        def is_chat_capable(card: ModelCard) -> bool:
            return "chat" in card.capabilities

        if manual:
            primary = attempts[0]
            if is_chat_capable(primary):
                return attempts
            raise ModelCapabilityError(
                f"{primary.display_name} is a vision/caption model and cannot answer text chat. "
                + self._chat_suggestion(cards)
            )
        capable = [card for card in attempts if is_chat_capable(card)]
        if capable:
            return capable
        broadened = [
            card
            for card in cards
            if is_chat_capable(card) and card.availability == "available"
        ]
        if broadened:
            return broadened
        raise ModelCapabilityError(
            "No currently available model supports text chat. " + self._chat_suggestion(cards)
        )

    @staticmethod
    def _chat_suggestion(cards: list[ModelCard]) -> str:
        names = [
            card.display_name
            for card in cards
            if "chat" in card.capabilities and card.availability == "available"
        ]
        if names:
            return f"Select a chat model such as: {', '.join(names[:5])}."
        return "Install a chat model (e.g. `ollama pull llama3.2:3b`)."

    def _route_attempts(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None,
        task_kind: TaskKind | str | None,
        allow_fallback: bool | None,
        images: list[tuple[bytes, str]] | None,
    ) -> tuple[TaskKind, list[ModelCard], list[ChatMessage]]:
        text = _user_text(messages)
        kind = (
            task_kind
            if isinstance(task_kind, TaskKind)
            else parse_task_kind(task_kind if isinstance(task_kind, str) else None, text)
        )
        cards = self._cards()
        attempts = self._attempts(cards, model=model, kind=kind, allow_fallback=allow_fallback)
        if not attempts:
            raise GatewayError(MODEL_UNAVAILABLE, self._unavailable_message(cards))
        manual = self._is_manual_request(model)
        if images:
            attempts = self._require_vision(attempts, cards, manual=manual)
        else:
            attempts = self._require_chat(attempts, cards, manual=manual)
            # Never silently replace a manual cloud/local pick with another model.
            attempts = _prefer_fast_local(
                attempts, kind=kind, text=text, cards=cards, manual=manual
            )
        prepared = _attach_images(messages, images) if images else messages
        return kind, attempts, prepared

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        task_kind: TaskKind | str | None = None,
        allow_fallback: bool | None = None,
        images: list[tuple[bytes, str]] | None = None,
    ) -> GatewayResult:
        self._raise_if_kill_switch()
        # Availability refresh is cached; never block chat on a cold tags fetch
        # when we already have a warm catalog.
        if self._models._ollama_reachable is None:
            await self.refresh_ollama()
        else:
            await self.refresh_ollama(force=False)
        kind, attempts, prepared = self._route_attempts(
            messages, model=model, task_kind=task_kind, allow_fallback=allow_fallback, images=images
        )
        logger.info(
            "gateway chat task=%s candidates=%d selection=%s images=%d primary=%s",
            kind.value,
            len(attempts),
            self._selection.mode,
            len(images) if images else 0,
            attempts[0].model_id if attempts else None,
        )
        return await self._run_chat(
            prepared,
            attempts,
            task_kind=kind,
            selection_mode=self._selection.mode,
        )
    async def _run_chat(
        self,
        messages: list[ChatMessage],
        attempts: list[ModelCard],
        *,
        task_kind: TaskKind | None = None,
        selection_mode: str | None = None,
    ) -> GatewayResult:
        last_error: GatewayError | None = None
        failed_from: str | None = None
        for index, card in enumerate(attempts):
            if card.availability == "unavailable" and card.availability_reason == "missing_api_key":
                error = missing_api_key_error(card.provider)
                if not self._should_continue(error, index, attempts):
                    raise error
                last_error = error
                failed_from = failed_from or card.model_id
                continue
            try:
                provider = self._open(card)
                text = await provider.chat(messages)
            except GatewayError as exc:
                logger.warning(
                    "gateway chat failed code=%s provider=%s model=%s",
                    exc.code,
                    card.provider,
                    card.model_id,
                )
                if not self._should_continue(exc, index, attempts):
                    raise
                last_error = exc
                failed_from = failed_from or card.model_id
                continue
            except Exception as exc:  # noqa: BLE001
                error = normalize_provider_error(exc, provider=card.provider, model=card.model_id)
                logger.warning(
                    "gateway chat failed code=%s provider=%s model=%s",
                    error.code,
                    card.provider,
                    card.model_id,
                )
                if not self._should_continue(error, index, attempts):
                    raise error
                last_error = error
                failed_from = failed_from or card.model_id
                continue
            result = GatewayResult(
                text=text,
                provider=provider.name,
                model_id=provider.model_name,
                display_name=card.display_name,
                fallback_used=index > 0,
                fallback_from=failed_from if index > 0 else None,
                task_kind=task_kind.value if task_kind else None,
                selection_mode=selection_mode,
            )
            self._last = result
            logger.info(
                "gateway chat completed provider=%s model=%s fallback=%s task=%s mode=%s",
                result.provider,
                result.model_id,
                result.fallback_used,
                result.task_kind,
                result.selection_mode,
            )
            return result
        if last_error is not None:
            raise last_error
        raise GatewayError(MODEL_UNAVAILABLE, self._unavailable_message(self._cards()))
    def _should_continue(self, error: GatewayError, index: int, attempts: list[ModelCard]) -> bool:
        if index >= len(attempts) - 1:
            return False
        if not error.retryable:
            return False
        # Auto always continues on transient errors. Manual continues only
        # when the user allowed fallback (extra attempts were added).
        return True
    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        task_kind: TaskKind | str | None = None,
        allow_fallback: bool | None = None,
        images: list[tuple[bytes, str]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        self._raise_if_kill_switch()
        if self._models._ollama_reachable is None:
            await self.refresh_ollama()
        else:
            await self.refresh_ollama(force=False)
        kind, attempts, prepared = self._route_attempts(
            messages, model=model, task_kind=task_kind, allow_fallback=allow_fallback, images=images
        )
        logger.info(
            "gateway stream task=%s candidates=%d selection=%s primary=%s",
            kind.value,
            len(attempts),
            self._selection.mode,
            attempts[0].model_id if attempts else None,
        )
        last_error: GatewayError | None = None
        failed_from: str | None = None
        for index, card in enumerate(attempts):
            if not card.supports_streaming:
                continue
            yielded = False
            try:
                provider = self._open(card)
                async for chunk in provider.stream(prepared):
                    yielded = True
                    yield StreamEvent(
                        type="delta",
                        text=chunk,
                        provider=provider.name,
                        model=provider.model_name,
                        display_name=card.display_name,
                    )
            except GatewayError as exc:
                if yielded or not self._should_continue(exc, index, attempts):
                    raise
                last_error = exc
                failed_from = failed_from or card.model_id
                continue
            except Exception as exc:  # noqa: BLE001
                error = normalize_provider_error(exc, provider=card.provider, model=card.model_id)
                if yielded or not self._should_continue(error, index, attempts):
                    raise error
                last_error = error
                failed_from = failed_from or card.model_id
                continue
            result = GatewayResult(
                text="",
                provider=card.provider,
                model_id=card.model_id,
                display_name=card.display_name,
                fallback_used=index > 0,
                fallback_from=failed_from if index > 0 else None,
                task_kind=kind.value,
                selection_mode=self._selection.mode,
            )
            self._last = result
            yield StreamEvent(
                type="done",
                provider=result.provider,
                model=result.model_id,
                display_name=result.display_name,
                fallback_used=result.fallback_used,
                fallback_from=result.fallback_from,
                task_kind=result.task_kind,
                selection_mode=result.selection_mode,
            )
            return
        if last_error is not None:
            raise last_error
        raise GatewayError(MODEL_UNAVAILABLE, "No streaming model is available.")
    async def check(self, model_id: str, *, live: bool = False) -> ModelCard:
        await self.refresh_ollama(force=True)
        cards = self._cards()
        card = find_card(cards, model_id, None)
        if card is None:
            if not is_safe_model_id(model_id) or contains_secret(model_id):
                raise GatewayError(MODEL_UNAVAILABLE, "Invalid model id.")
            raise GatewayError(
                MODEL_UNAVAILABLE,
                "The requested model is not in the registry.",
                model=model_id,
            )
        if card.availability != "available" or not live:
            return card
        try:
            provider = self._open(card)
            healthy = await provider.health_check()
        except GatewayError as exc:
            if exc.code == AUTHENTICATION_ERROR:
                return card.model_copy(
                    update={"availability": "unavailable", "availability_reason": "missing_api_key"}
                )
            return card.model_copy(
                update={"availability": "unavailable", "availability_reason": "provider_unavailable"}
            )
        except Exception:  # noqa: BLE001
            healthy = False
        if not healthy:
            return card.model_copy(
                update={"availability": "unavailable", "availability_reason": "provider_unavailable"}
            )
        return card
    def active_card(self) -> ModelCard:
        cards = self._cards()
        if self._selection.mode == "manual" and self._selection.provider and self._selection.model_id:
            return self._card(self._selection.provider, self._selection.model_id, cards)
        kind = TaskKind.LOCAL if self._settings.ai_provider in ("local", "ollama") else TaskKind.SIMPLE
        ordered = self._policy.candidates(
            kind,
            cards,
            allow_cloud_for_local=self._selection.allow_fallback,
        )
        if ordered:
            return ordered[0]
        if self._selection.provider and self._selection.model_id:
            return self._card(self._selection.provider, self._selection.model_id, cards)
        return ModelCard(
            provider=self._settings.ai_provider,
            model_id="unavailable",
            display_name="Unavailable",
            availability="unavailable",
            availability_reason="model_unavailable",
        )
    async def health_check(self) -> bool:
        try:
            await self.refresh_ollama()
            card = self.active_card()
            if card.availability != "available":
                return False
            provider = self._open(card)
            return await provider.health_check()
        except Exception:  # noqa: BLE001
            return False
def build_model_gateway(settings: Settings) -> ModelGateway:
    return ModelGateway(
        providers=build_provider_registry(settings),
        models=ModelRegistry(static_catalog()),
        settings=settings,
    )
def _attach_images(messages: list[ChatMessage], images: list[tuple[bytes, str]]) -> list[ChatMessage]:
    """Return a copy of ``messages`` with ``images`` attached to the last user turn."""
    encoded = [
        ImageAttachment(data_base64=base64.b64encode(raw).decode("ascii"), mime_type=mime)
        for raw, mime in images
    ]
    updated = list(messages)
    for index in range(len(updated) - 1, -1, -1):
        if updated[index].role == ChatRole.USER:
            updated[index] = updated[index].model_copy(update={"images": encoded})
            break
    return updated
def _user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role.value == "user":
            return message.content
    return ""


_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")
_SHORT_SIMPLE_RE = re.compile(
    r"^(привет|здравствуй|здравствуйте|hello|hi|hey|добрый\s+(день|вечер|утро)|ок|ok|да|нет)[\s!.?…]*$",
    re.IGNORECASE,
)


def _param_billions(model_id: str) -> float:
    match = _PARAM_RE.search(model_id)
    if match:
        return float(match.group(1))
    # Unknown size — treat as mid/large so known small models win the fast path.
    return 7.0


def _prefer_fast_local(
    attempts: list[ModelCard],
    *,
    kind: TaskKind,
    text: str,
    cards: list[ModelCard],
    manual: bool = False,
) -> list[ModelCard]:
    """For simple/short chat, put the smallest suitable local chat model first.

    Does not invent answers — only reorders real available models. Skips
    vision-only cards. Keeps non-local models after local fast candidates.
    Manual selections are never reordered (cloud keys / user pick stay honest).
    """
    if manual:
        return attempts
    if kind not in (TaskKind.SIMPLE, TaskKind.LOCAL):
        return attempts
    stripped = text.strip()
    if len(stripped) > 120 and not _SHORT_SIMPLE_RE.match(stripped):
        return attempts
    local_chat = [
        card
        for card in cards
        if card.provider in ("ollama", "local")
        and card.availability == "available"
        and "chat" in card.capabilities
    ]
    if not local_chat:
        return attempts
    # Prefer ~1–2B (quality + usually already warm). Sub-1B only as last resort —
    # swapping models mid-session pays a full cold load and hurts TTFT.
    def rank(card: ModelCard) -> tuple[float, str]:
        size = _param_billions(card.model_id)
        penalty = 0.0 if 1.0 <= size <= 3.0 else (20.0 if size < 1.0 else size)
        return (penalty + size, card.model_id)

    local_chat.sort(key=rank)
    fastest = local_chat[0]
    if attempts and _same(attempts[0], fastest):
        return attempts
    rest = [card for card in attempts if not _same(card, fastest)]
    logger.info(
        "gateway fast-route primary=%s task=%s text_len=%d",
        fastest.model_id,
        kind.value,
        len(stripped),
    )
    return [fastest, *rest]


def _key_for(settings: Settings, provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "gemini":
        return bool(settings.resolved_gemini_api_key)
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
    return True
def _same(left: ModelCard, right: ModelCard) -> bool:
    return left.provider == right.provider and left.model_id == right.model_id
def _dedupe(cards: list[ModelCard]) -> list[ModelCard]:
    seen: set[tuple[str, str]] = set()
    result: list[ModelCard] = []
    for card in cards:
        key = (card.provider, card.model_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(card)
    return result
