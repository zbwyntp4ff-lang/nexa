"""Chat endpoint - the main entry point into NEXA Core."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.beta.guest_quota import consume_guest_request

from app.api.deps import (
    get_auth_service,
    get_memory_manager_dep,
    get_nexa_core,
    get_profile_service,
    get_settings,
    get_token_service,
)
from app.api.routes.auth import _extract_token
from app.auth.errors import UnauthorizedError
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import Settings
from app.core.nexa_core import NexaCore
from app.gateway.models import StreamEvent
from app.learning.memory_context import build_memory_hint
from app.learning.settings import get_learning_settings
from app.memory.manager import MemoryManager
from app.models.chat import ChatRequest, ChatResponse
from app.models.errors import NexaError
from app.profile.models import ProjectPersonalization
from app.profile.service import ProfileService
from app.tokens.guard import resolve_request_id, run_with_token_charge
from app.tokens.service import TokenService

router = APIRouter(prefix="/api/v1", tags=["chat"])
_bearer = HTTPBearer(auto_error=False)


def resolve_chat_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRecord | None:
    if settings.nexa_public_beta:
        # Every visitor on the public-beta host uses the same guest allowance,
        # even if an old account cookie is present in this browser.
        consume_guest_request(request)
        return None
    token = _extract_token(request, credentials)
    if not token:
        if settings.tokens_enforce:
            raise UnauthorizedError()
        return None
    try:
        return auth.get_user_for_token(token)
    except UnauthorizedError:
        if settings.tokens_enforce:
            raise
        return None


def _apply_public_beta_restrictions(
    request: ChatRequest,
    user: UserRecord | None,
    settings: Settings,
) -> ChatRequest:
    """Keep anonymous beta traffic on the default text-chat path."""
    if not settings.nexa_public_beta or user is not None:
        return request
    return request.model_copy(
        update={
            "model": None,
            "task": None,
            "attachment_ids": [],
            "use_knowledge_base": False,
            "knowledge_project_id": None,
            "knowledge_conversation_id": None,
            "knowledge_top_k": None,
            "project_personalization": None,
            "apply_personalization": False,
        }
    )


def _with_learning_context(
    request: ChatRequest,
    user: UserRecord | None,
    profiles: ProfileService,
    memory: MemoryManager,
) -> ChatRequest:
    """Attach personalization + approved memory; optionally enable RAG.

    Client-supplied ``server_personalization_hint`` is always ignored.
    ``use_knowledge_base`` from the client remains an explicit opt-in; when
    learning settings enable auto KB and the client did not set it, we enable RAG.
    """
    request = request.model_copy(
        update={"server_personalization_hint": None, "knowledge_user_id": None}
    )
    learning = get_learning_settings()
    updates: dict = {}
    if user is not None:
        updates["knowledge_user_id"] = user.id

    # Prefer RAG when Learning auto-KB is on, client did not opt in yet, and docs exist.
    # Explicit client ``use_knowledge_base=True`` is unchanged; we never invent sources.
    if learning.auto_knowledge_base and not request.use_knowledge_base:
        try:
            from app.knowledge.knowledge_base import get_knowledge_base

            docs = get_knowledge_base().list_documents(
                user_id=user.id if user is not None else None
            )
            if docs:
                updates["use_knowledge_base"] = True
        except Exception:  # noqa: BLE001
            pass

    hints: list[str] = []
    if user is not None and request.apply_personalization:
        project = None
        if request.project_personalization:
            try:
                project = ProjectPersonalization.model_validate(request.project_personalization)
            except Exception:  # noqa: BLE001
                project = None
        profiles.get_or_create(user.id)
        profile_hint = profiles.compact_hint(user.id, project)
        if profile_hint:
            hints.append(profile_hint)
        preferred = profiles.preferred_model(user.id, project)
        if preferred and not request.model:
            updates["model"] = preferred

    if user is not None and learning.memory_enabled:
        mem_hint = build_memory_hint(
            memory,
            user_id=user.id,
            query=request.message,
            enabled=True,
        )
        if mem_hint:
            hints.append(mem_hint)

    if hints:
        updates["server_personalization_hint"] = "\n".join(hints)
    return request.model_copy(update=updates) if updates else request


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    core: NexaCore = Depends(get_nexa_core),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    user: UserRecord | None = Depends(resolve_chat_user),
    profiles: ProfileService = Depends(get_profile_service),
    memory: MemoryManager = Depends(get_memory_manager_dep),
    x_request_id: Annotated[str | None, Header()] = None,
) -> ChatResponse:
    request = _with_learning_context(request, user, profiles, memory)
    request = _apply_public_beta_restrictions(request, user, settings)
    if user is None or not settings.tokens_enforce:
        return await core.chat(request)

    rid = resolve_request_id(getattr(request, "request_id", None), x_request_id)

    async def _work() -> ChatResponse:
        return await core.chat(request)

    return await run_with_token_charge(
        tokens,
        user_id=user.id,
        amount=tokens.cost_chat,
        request_id=rid,
        reason="chat",
        work=_work,
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    core: NexaCore = Depends(get_nexa_core),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    user: UserRecord | None = Depends(resolve_chat_user),
    profiles: ProfileService = Depends(get_profile_service),
    memory: MemoryManager = Depends(get_memory_manager_dep),
    x_request_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Server-sent events. Each event is a JSON object (meta, delta, or done)."""
    request = _with_learning_context(request, user, profiles, memory)
    request = _apply_public_beta_restrictions(request, user, settings)
    rid = resolve_request_id(getattr(request, "request_id", None), x_request_id)

    async def events() -> AsyncIterator[str]:
        charged = False
        try:
            if user is not None and settings.tokens_enforce:
                tokens.charge(
                    user.id,
                    tokens.cost_chat,
                    request_id=rid,
                    reason="chat_stream",
                )
                charged = True
            async for event in core.stream_events(request):
                yield f"data: {event.model_dump_json()}\n\n"
        except NexaError as exc:
            if charged:
                tokens.refund(rid, reason="ai_error_refund")
            code = getattr(exc, "code", None) or exc.__class__.__name__
            payload = StreamEvent(type="error", error=str(code), message=exc.message)
            yield f"data: {payload.model_dump_json()}\n\n"
        except Exception:
            if charged:
                tokens.refund(rid, reason="ai_error_refund")
            raise

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
