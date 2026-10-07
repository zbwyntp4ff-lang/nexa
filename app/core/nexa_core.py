"""NEXA Core - the provider-agnostic orchestrator for chat requests.
``NexaCore`` never imports a concrete provider module directly. It only knows
about the :class:`app.providers.base.AIProvider` interface, and receives a
concrete instance via dependency injection (normally produced by
:class:`app.providers.factory.ProviderFactory`). This keeps the core stable
even as new providers (including a future first-party ``nexa`` provider) are
added.
"""
from __future__ import annotations
import asyncio
import time
from app.attachments.manager import AttachmentManager
from app.attachments.models import AttachmentKind, AttachmentStatus
from app.config.settings import Settings
from app.core.logging_config import get_logger
from app.knowledge.knowledge_base import KnowledgeBase
from app.knowledge.models import RetrievalResult
from app.models.chat import ChatCitation, ChatMessage, ChatRequest, ChatResponse, ChatRole
from app.models.errors import (
    AttachmentValidationError,
    EmptyMessageError,
    MessageTooLongError,
    ModelCapabilityError,
    ModelError,
    NexaError,
    ProviderTimeoutError,
    TooManyAttachmentsError,
)
from app.gateway.gateway import ModelGateway
from app.gateway.models import StreamEvent
from app.knowledge_core.composer import KnowledgeCoreComposer
from app.models.status import ModelInfoResponse
from app.providers.base import AIProvider
logger = get_logger("nexa.core")
_knowledge_core = KnowledgeCoreComposer()

# Keep the default prompt short — long system text dominates local-model prefill/TTFT.
_FAST_SYSTEM_PROMPT = (
    "You are NEXA, a desktop AI assistant. "
    "Reply in the user's language, briefly and correctly. Never mix languages."
)

_CAPABILITY_SYSTEM_PROMPT = (
    f"{_FAST_SYSTEM_PROMPT} "
    "If asked what you can do, answer as a vertical «- » list only: "
    "Chat, Agent, Code, Research, Create (images), Vision, files, Omniverse/HEXA. "
    "Do not invent unrelated products."
)

_CYRILLIC_HINT = "Отвечай грамотным русским, без латиницы в словах."

# Recent turns only — full history hurts local prefill latency.
_MAX_HISTORY_MESSAGES = 8

_CAPABILITY_ASK_RE = __import__("re").compile(
    r"(что\s+ты\s+умеешь|на\s+что\s+ты\s+способ|what\s+can\s+you\s+do|your\s+capabilities)",
    __import__("re").IGNORECASE,
)


def _has_cyrillic(text: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)


def _trim_history(history: list[ChatMessage], limit: int = _MAX_HISTORY_MESSAGES) -> list[ChatMessage]:
    if len(history) <= limit:
        return history
    return history[-limit:]


class NexaCore:
    """Core business logic: validation, orchestration, logging."""
    def __init__(
        self,
        provider: AIProvider,
        settings: Settings,
        gateway: ModelGateway | None = None,
        attachments: AttachmentManager | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self.gateway = gateway
        self.attachments = attachments
        self.knowledge_base = knowledge_base
    @property
    def provider(self) -> AIProvider:
        return self._provider
    def _validate(self, message: str) -> None:
        if not message or not message.strip():
            raise EmptyMessageError()
        if len(message) > self._settings.max_message_length:
            raise MessageTooLongError(len(message), self._settings.max_message_length)
    def _build_messages(self, request: ChatRequest) -> list[ChatMessage]:
        history = _trim_history([m for m in request.history if m.role != ChatRole.SYSTEM])
        has_system = any(m.role == ChatRole.SYSTEM for m in request.history)
        messages: list[ChatMessage] = []
        if not has_system:
            if _CAPABILITY_ASK_RE.search(request.message):
                system = _CAPABILITY_SYSTEM_PROMPT
            else:
                system = _FAST_SYSTEM_PROMPT
            if _has_cyrillic(request.message):
                system = f"{system} {_CYRILLIC_HINT}"
            # Intent-selected Knowledge Core packs (structured rules, not one mega-prompt).
            core = _knowledge_core.compose(request.message, task=request.task)
            if core.text:
                system = f"{system}\n\n{core.text}"
                logger.info(
                    "knowledge_core injected intents=%s packs=%s chars=%d",
                    ",".join(i.value for i in core.intents),
                    ",".join(core.pack_ids),
                    core.char_count,
                )
            messages.append(ChatMessage(role=ChatRole.SYSTEM, content=system))
        else:
            # Keep at most one leading system message from the client (e.g. Code mode).
            for item in request.history:
                if item.role == ChatRole.SYSTEM:
                    messages.append(item)
                    break
            # Still attach Knowledge Core after client system (e.g. Code mode + build rules).
            core = _knowledge_core.compose(request.message, task=request.task or "coding")
            if core.text:
                messages.append(ChatMessage(role=ChatRole.SYSTEM, content=core.text))
        messages.extend(history)
        messages.append(ChatMessage(role=ChatRole.USER, content=request.message))
        return messages
    def _resolve_attachments(
        self, request: ChatRequest
    ) -> tuple[list[ChatMessage], list[tuple[bytes, str]], list[str]]:
        """Turn ``request.attachment_ids`` into extra context + image payloads.
        Documents become a bounded "Document Context" system message (never
        the full raw file). Images become provider-agnostic byte payloads
        that :class:`app.gateway.gateway.ModelGateway` only sends to models
        that declare ``supports_vision``.
        Raises:
            app.models.errors.TooManyAttachmentsError
            app.models.errors.AttachmentNotFoundError
            app.models.errors.AttachmentValidationError
            app.models.errors.ModelCapabilityError
        """
        messages = self._build_messages(request)
        if not request.attachment_ids:
            return messages, [], []
        if len(request.attachment_ids) > self._settings.max_attachments_per_message:
            raise TooManyAttachmentsError(
                f"This request has {len(request.attachment_ids)} attachments, exceeding the "
                f"maximum of {self._settings.max_attachments_per_message}."
            )
        if self.attachments is None:
            raise ModelCapabilityError("Attachments are not available on this server.")
        records = self.attachments.resolve_ids(request.attachment_ids)
        failed = [r for r in records if r.status == AttachmentStatus.FAILED]
        if failed:
            raise AttachmentValidationError(
                "These attachments failed to process and cannot be used: "
                + ", ".join(r.filename for r in failed)
                + "."
            )
        pending = [r for r in records if r.status == AttachmentStatus.PROCESSING]
        if pending:
            raise AttachmentValidationError(
                "These attachments are still processing, try again shortly: "
                + ", ".join(r.filename for r in pending)
                + "."
            )
        doc_ids = [r.id for r in records if r.kind == AttachmentKind.DOCUMENT]
        image_ids = [r.id for r in records if r.kind == AttachmentKind.IMAGE]
        if doc_ids:
            context = self.attachments.document_context(doc_ids, query=request.message)
            if context:
                messages = [
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=(
                            "Document context from files the user attached to this message "
                            "(may be a partial excerpt, not the full document):\n\n" + context
                        ),
                    ),
                    *messages,
                ]
        images = self.attachments.image_payloads(image_ids) if image_ids else []
        return messages, images, [r.id for r in records]
    def _resolve_knowledge(self, request: ChatRequest) -> tuple[list[ChatMessage], RetrievalResult | None]:
        """Opt-in RAG step: retrieve, then prepend a labeled context message.
        Returns unchanged messages (an empty list marker) when the caller
        didn't ask for it - existing chat behavior is completely unaffected
        unless ``use_knowledge_base`` is explicitly set.
        """
        if not request.use_knowledge_base or self.knowledge_base is None:
            return [], None
        result = self.knowledge_base.search(
            request.message,
            project_id=request.knowledge_project_id,
            conversation_id=request.knowledge_conversation_id,
            top_k=request.knowledge_top_k,
        )
        context_message = ChatMessage(
            role=ChatRole.SYSTEM, content=self.knowledge_base.build_context_message(result)
        )
        return [context_message], result
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Validate, dispatch to the provider, and return a ``ChatResponse``.
        Raises:
            app.models.errors.EmptyMessageError
            app.models.errors.MessageTooLongError
            app.models.errors.ModelError
            app.models.errors.ProviderTimeoutError
        """
        self._validate(request.message)
        prep_started = time.perf_counter()
        if request.attachment_ids:
            messages, images, attachments_used = self._resolve_attachments(request)
        else:
            messages = self._build_messages(request)
            images = []
            attachments_used = []
        if images and self.gateway is None:
            raise ModelCapabilityError("Image input requires the model gateway.")
        if request.use_knowledge_base:
            knowledge_messages, knowledge_result = self._resolve_knowledge(request)
            messages = [*knowledge_messages, *messages]
        else:
            knowledge_result = None
        prep_ms = (time.perf_counter() - prep_started) * 1000
        logger.info(
            "chat request received provider=%s model=%s message_len=%d attachments=%d knowledge=%s prep_ms=%.1f",
            self._provider.name,
            self._provider.model_name,
            len(request.message),
            len(attachments_used),
            bool(knowledge_result and not knowledge_result.insufficient),
            prep_ms,
        )
        start = time.perf_counter()
        try:
            if self.gateway is not None:
                result = await asyncio.wait_for(
                    self.gateway.chat(
                        messages, model=request.model, task_kind=request.task, images=images or None
                    ),
                    timeout=self._settings.request_timeout_seconds,
                )
                text = result.text
                provider_name = result.provider
                model_name = result.model_id
                display_name = result.display_name
                fallback_used = result.fallback_used
                fallback_from = result.fallback_from
            else:
                text = await asyncio.wait_for(
                    self._provider.generate(messages),
                    timeout=self._settings.request_timeout_seconds,
                )
                provider_name = self._provider.name
                model_name = self._provider.model_name
                display_name = None
                fallback_used = False
                fallback_from = None
        except asyncio.TimeoutError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "chat request timed out provider=%s model=%s elapsed_ms=%.1f",
                self._provider.name,
                self._provider.model_name,
                elapsed_ms,
            )
            raise ProviderTimeoutError() from exc
        except NexaError:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "chat request failed provider=%s model=%s elapsed_ms=%.1f",
                self._provider.name,
                self._provider.model_name,
                elapsed_ms,
            )
            raise
        except Exception as exc:  # noqa: BLE001 - never leak raw stack traces
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "chat request errored provider=%s model=%s elapsed_ms=%.1f error=%s",
                self._provider.name,
                self._provider.model_name,
                elapsed_ms,
                exc.__class__.__name__,
            )
            raise ModelError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "chat timings prep_ms=%.1f provider_ms=%.1f total_ms=%.1f model_calls=1 provider=%s model=%s",
            prep_ms,
            elapsed_ms,
            prep_ms + elapsed_ms,
            provider_name,
            model_name,
        )
        citations = (
            [ChatCitation(**c.model_dump()) for c in knowledge_result.citations]
            if knowledge_result and not knowledge_result.insufficient
            else []
        )
        return ChatResponse(
            message=text,
            provider=provider_name,
            model=model_name,
            display_name=display_name,
            fallback_used=fallback_used,
            fallback_from=fallback_from,
            attachments_used=attachments_used,
            citations=citations,
            knowledge_used=bool(request.use_knowledge_base),
            latency_ms=round(elapsed_ms, 2),
        )
    async def stream_events(self, request: ChatRequest):
        """Yield streaming events after the request has been validated."""
        received_at = time.perf_counter()
        self._validate(request.message)
        # Skip attachment/knowledge work when unused — common path for plain chat.
        if request.attachment_ids:
            messages, images, _attachments_used = self._resolve_attachments(request)
        else:
            messages = self._build_messages(request)
            images = []
        if images and self.gateway is None:
            raise ModelCapabilityError("Image input requires the model gateway.")
        if request.use_knowledge_base:
            knowledge_messages, knowledge_result = self._resolve_knowledge(request)
            messages = [*knowledge_messages, *messages]
        else:
            knowledge_result = None
        citations = (
            [c.model_dump(mode="json") for c in knowledge_result.citations]
            if knowledge_result and not knowledge_result.insufficient
            else []
        )
        prep_ms = (time.perf_counter() - received_at) * 1000
        logger.info(
            "chat stream received prep_ms=%.1f message_len=%d history=%d attachments=%d",
            prep_ms,
            len(request.message),
            len(request.history),
            len(request.attachment_ids or []),
        )
        yield StreamEvent(type="meta", backend_received_ms=round(prep_ms, 2))
        started = time.perf_counter()
        provider_start_ms = (started - received_at) * 1000
        first = True
        ttft_ms: float | None = None
        if self.gateway is not None:
            async for event in self.gateway.stream(
                messages, model=request.model, task_kind=request.task, images=images or None
            ):
                if event.type == "delta" and first:
                    first = False
                    ttft_ms = (time.perf_counter() - received_at) * 1000
                    logger.info(
                        "chat stream first token ttft_ms=%.1f prep_ms=%.1f",
                        ttft_ms,
                        prep_ms,
                    )
                if event.type == "done":
                    total_ms = (time.perf_counter() - received_at) * 1000
                    updates: dict = {
                        "ttft_ms": round(ttft_ms, 2) if ttft_ms is not None else None,
                        "total_ms": round(total_ms, 2),
                        "backend_received_ms": round(prep_ms, 2),
                        "provider_start_ms": round(provider_start_ms, 2),
                    }
                    if citations:
                        updates["citations"] = citations
                    event = event.model_copy(update=updates)
                    logger.info(
                        "chat stream done ttft_ms=%s total_ms=%.1f",
                        f"{ttft_ms:.1f}" if ttft_ms is not None else "none",
                        total_ms,
                    )
                yield event
            return
        async for chunk in self._provider.stream(messages):
            if first:
                first = False
                ttft_ms = (time.perf_counter() - received_at) * 1000
                logger.info("chat stream first token ttft_ms=%.1f", ttft_ms)
            yield StreamEvent(
                type="delta",
                text=chunk,
                provider=self._provider.name,
                model=self._provider.model_name,
            )
        total_ms = (time.perf_counter() - received_at) * 1000
        logger.info(
            "chat stream done ttft_ms=%s total_ms=%.1f",
            f"{ttft_ms:.1f}" if ttft_ms is not None else "none",
            total_ms,
        )
        yield StreamEvent(
            type="done",
            provider=self._provider.name,
            model=self._provider.model_name,
            citations=citations,
            ttft_ms=round(ttft_ms, 2) if ttft_ms is not None else None,
            total_ms=round(total_ms, 2),
            backend_received_ms=round(prep_ms, 2),
            provider_start_ms=round(provider_start_ms, 2),
        )
    def prepare_chat(self, request: ChatRequest) -> list[ChatMessage]:
        """Lightweight validation only — heavy prep belongs inside the stream generator."""
        self._validate(request.message)
        return []
    def active_identity(self) -> tuple[str, str]:
        if self.gateway is not None:
            card = self.gateway.active_card()
            return card.provider, card.model_id
        return self._provider.name, self._provider.model_name
    def model_info(self) -> ModelInfoResponse:
        if self.gateway is None:
            return ModelInfoResponse(provider=self._provider.name, model=self._provider.model_name)
        card = self.gateway.active_card()
        last = self.gateway.last_result
        return ModelInfoResponse(
            provider=card.provider,
            model=card.model_id,
            display_name=card.display_name,
            selection_mode=self.gateway.selection.mode,
            allow_fallback=self.gateway.selection.allow_fallback,
            availability=card.availability,
            availability_reason=card.availability_reason,
            last_provider=last.provider if last else None,
            last_model=last.model_id if last else None,
            last_display_name=last.display_name if last else None,
        )
    async def health_check(self) -> bool:
        try:
            if self.gateway is not None:
                return await self.gateway.health_check()
            return await self._provider.health_check()
        except Exception:  # noqa: BLE001
            return False
