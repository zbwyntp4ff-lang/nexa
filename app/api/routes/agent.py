"""Agent endpoint - runs the Part 2 Agent loop."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.agent.agent import Agent
from app.agent.models import AgentTask
from app.api.deps import get_agent, get_auth_service, get_settings, get_token_service
from app.api.routes.auth import _extract_token
from app.attachments.manager import AttachmentManager, get_attachment_manager
from app.auth.errors import UnauthorizedError
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.config.settings import Settings
from app.models.agent_api import AgentRunRequest, AgentRunResponse
from app.tokens.guard import resolve_request_id, run_with_token_charge
from app.tokens.service import TokenService

router = APIRouter(prefix="/api/v1", tags=["agent"])
_bearer = HTTPBearer(auto_error=False)


def _resolve_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRecord | None:
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


@router.post("/agent", response_model=AgentRunResponse)
async def run_agent(
    request: AgentRunRequest,
    agent: Agent = Depends(get_agent),
    attachments: AttachmentManager = Depends(get_attachment_manager),
    tokens: TokenService = Depends(get_token_service),
    settings: Settings = Depends(get_settings),
    user: UserRecord | None = Depends(_resolve_user),
    x_request_id: Annotated[str | None, Header()] = None,
) -> AgentRunResponse:
    context = (
        attachments.document_context(request.attachment_ids, query=request.task)
        if request.attachment_ids
        else None
    )
    task = AgentTask(
        description=request.task,
        dry_run=request.dry_run,
        context=context or None,
        disabled_tools=frozenset(request.disabled_tools),
        metadata={"user_id": user.id} if user is not None else {},
    )

    from app.agent.concurrency import release_agent_slot, try_acquire_agent_slot

    slot = await try_acquire_agent_slot(user.id if user is not None else None)

    async def _work() -> AgentRunResponse:
        result = await agent.run(task)
        return AgentRunResponse(**result.model_dump())

    try:
        if user is None or not settings.tokens_enforce:
            return await _work()

        rid = resolve_request_id(x_request_id)
        return await run_with_token_charge(
            tokens,
            user_id=user.id,
            amount=tokens.cost_agent,
            request_id=rid,
            reason="agent",
            work=_work,
        )
    finally:
        release_agent_slot(slot)
