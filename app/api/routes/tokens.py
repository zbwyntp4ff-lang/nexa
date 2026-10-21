"""HTTP API for internal AI token balances (user + admin)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_auth_service, get_token_service
from app.api.routes.auth import get_current_user
from app.auth.models import UserRecord
from app.auth.service import AuthService
from app.models.tokens_api import (
    AdminAmountRequest,
    AdminLimitsRequest,
    LedgerEntryPublic,
    TokenBalanceResponse,
    TokenCostsPublic,
    TokenHistoryResponse,
    UsageByReasonPublic,
)
from app.tokens.errors import TokenAdminRequiredError
from app.tokens.service import TokenService

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


def require_token_admin(
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRecord:
    if not auth.is_owner(user):
        raise TokenAdminRequiredError()
    return user


def _balance_response(
    account,
    tokens: TokenService | None = None,
    *,
    include_breakdown: bool = False,
) -> TokenBalanceResponse:
    costs = None
    usage: list[UsageByReasonPublic] = []
    if tokens is not None:
        schedule = tokens.cost_schedule()
        costs = TokenCostsPublic(**schedule)
        if include_breakdown:
            usage = [
                UsageByReasonPublic(**row)  # type: ignore[arg-type]
                for row in tokens.usage_by_reason(account.user_id)
            ]
    return TokenBalanceResponse(
        user_id=account.user_id,
        balance=account.balance,
        daily_limit=account.daily_limit,
        monthly_limit=account.monthly_limit,
        daily_spent=account.daily_spent,
        monthly_spent=account.monthly_spent,
        daily_period=account.daily_period,
        monthly_period=account.monthly_period,
        updated_at=account.updated_at,
        unit="nexa_credits",
        costs=costs,
        usage_by_reason=usage,
    )


@router.get("/balance", response_model=TokenBalanceResponse)
async def get_balance(
    user: Annotated[UserRecord, Depends(get_current_user)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenBalanceResponse:
    return _balance_response(
        tokens.get_balance(user.id), tokens, include_breakdown=True
    )


@router.get("/history", response_model=TokenHistoryResponse)
async def get_history(
    user: Annotated[UserRecord, Depends(get_current_user)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TokenHistoryResponse:
    items = tokens.get_history(user.id, limit=limit, offset=offset)
    return TokenHistoryResponse(
        items=[LedgerEntryPublic(**e.model_dump()) for e in items],
        limit=limit,
        offset=offset,
    )


@router.post("/admin/credit", response_model=TokenBalanceResponse)
async def admin_credit(
    body: AdminAmountRequest,
    admin: Annotated[UserRecord, Depends(require_token_admin)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenBalanceResponse:
    account = tokens.admin_credit(
        body.user_id,
        body.amount,
        actor_id=admin.id,
        reason=body.reason,
    )
    return _balance_response(account, tokens)


@router.post("/admin/debit", response_model=TokenBalanceResponse)
async def admin_debit(
    body: AdminAmountRequest,
    admin: Annotated[UserRecord, Depends(require_token_admin)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenBalanceResponse:
    account = tokens.admin_debit(
        body.user_id,
        body.amount,
        actor_id=admin.id,
        reason=body.reason,
    )
    return _balance_response(account, tokens)


@router.put("/admin/limits", response_model=TokenBalanceResponse)
async def admin_set_limits(
    body: AdminLimitsRequest,
    admin: Annotated[UserRecord, Depends(require_token_admin)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenBalanceResponse:
    if body.daily_limit is None and body.monthly_limit is None:
        from app.tokens.errors import InvalidTokenAmountError

        raise InvalidTokenAmountError("Provide daily_limit and/or monthly_limit.")
    account = tokens.admin_set_limits(
        body.user_id,
        daily_limit=body.daily_limit,
        monthly_limit=body.monthly_limit,
        actor_id=admin.id,
    )
    return _balance_response(account, tokens)


@router.get("/admin/balance/{user_id}", response_model=TokenBalanceResponse)
async def admin_get_balance(
    user_id: str,
    _: Annotated[UserRecord, Depends(require_token_admin)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> TokenBalanceResponse:
    return _balance_response(
        tokens.get_balance(user_id), tokens, include_breakdown=True
    )
