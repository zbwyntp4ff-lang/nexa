"""TokenService — sole entry point for AI credit balance / limits / ledger."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.tokens.errors import (
    DailyTokenLimitError,
    InsufficientTokensError,
    InvalidTokenAmountError,
    MonthlyTokenLimitError,
    TokenIdempotencyConflictError,
    DuplicateTokenRequestError,
)
from app.tokens.models import ChargeRecord, LedgerEntry, TokenAccount, utcnow
from app.tokens.store import TokenStore


def _day_key(now: datetime | None = None) -> str:
    return (now or utcnow()).astimezone(timezone.utc).strftime("%Y-%m-%d")


def _month_key(now: datetime | None = None) -> str:
    return (now or utcnow()).astimezone(timezone.utc).strftime("%Y-%m")


class TokenService:
    def __init__(
        self,
        store: TokenStore,
        *,
        default_balance: int = 100,
        default_daily_limit: int = 1_000,
        default_monthly_limit: int = 10_000,
        cost_chat: int = 1,
        cost_agent: int = 5,
        cost_image: int = 10,
        cost_default: int = 1,
    ) -> None:
        self._store = store
        self._default_balance = max(0, default_balance)
        self._default_daily = max(0, default_daily_limit)
        self._default_monthly = max(0, default_monthly_limit)
        self.cost_chat = max(0, cost_chat)
        self.cost_agent = max(0, cost_agent)
        self.cost_image = max(0, cost_image)
        self.cost_default = max(0, cost_default)

    # --- reads ---------------------------------------------------------------
    def get_or_create_account(self, user_id: str) -> TokenAccount:
        def _op(store: TokenStore) -> TokenAccount:
            acc = store.account_get(user_id)
            if acc is not None:
                return self._refresh_periods(store, acc)
            return self._bootstrap_account(store, user_id)

        return self._store.run_atomic(_op)

    def get_balance(self, user_id: str) -> TokenAccount:
        return self.get_or_create_account(user_id)

    def get_history(
        self, user_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[LedgerEntry]:
        self.get_or_create_account(user_id)
        return self._store.run_atomic(
            lambda s: s.ledger_list(user_id=user_id, limit=limit, offset=offset)
        )

    def cost_schedule(self) -> dict[str, int]:
        """Fixed NEXA credit prices per action (estimates — not provider tokens)."""
        return {
            "chat": self.cost_chat,
            "agent": self.cost_agent,
            "image": self.cost_image,
            "default": self.cost_default,
        }

    def usage_by_reason(self, user_id: str, *, limit: int = 500) -> list[dict[str, int | str]]:
        """Aggregate debit spend by ledger reason (NEXA credits only)."""
        entries = self.get_history(user_id, limit=limit, offset=0)
        buckets: dict[str, dict[str, int]] = {}
        for entry in entries:
            if entry.amount >= 0:
                continue
            reason = (entry.reason or "unknown").strip() or "unknown"
            bucket = buckets.setdefault(reason, {"spent": 0, "count": 0})
            bucket["spent"] += -entry.amount
            bucket["count"] += 1
        rows = [
            {"reason": reason, "spent": data["spent"], "count": data["count"]}
            for reason, data in buckets.items()
        ]
        rows.sort(key=lambda r: int(r["spent"]), reverse=True)
        return rows

    # --- charge / refund (AI path) -------------------------------------------
    def charge(
        self,
        user_id: str,
        amount: int,
        *,
        request_id: str,
        reason: str = "ai_request",
    ) -> TokenAccount:
        """
        Atomically debit ``amount`` for ``request_id``.

        Idempotent: repeating the same ``request_id`` returns the account
        without a second debit (retry-safe).
        """
        if amount <= 0:
            raise InvalidTokenAmountError()
        if not request_id or not request_id.strip():
            raise InvalidTokenAmountError("request_id is required.")

        request_id = request_id.strip()

        def _op(store: TokenStore) -> TokenAccount:
            existing = store.charge_get(request_id, user_id)
            if existing is not None:
                # An idempotency key is bound to both owner and operation details.
                if existing.amount != amount or existing.reason != reason:
                    raise TokenIdempotencyConflictError()
                # A charge record is also an execution guard. Returning the
                # account here would let the route run the expensive AI work
                # again without a second debit.
                raise DuplicateTokenRequestError()

            acc = store.account_get(user_id)
            if acc is None:
                acc = self._bootstrap_account(store, user_id)
            else:
                acc = self._refresh_periods(store, acc)

            if acc.balance < amount:
                raise InsufficientTokensError(balance=acc.balance, required=amount)
            if acc.daily_limit >= 0 and acc.daily_spent + amount > acc.daily_limit:
                raise DailyTokenLimitError(used=acc.daily_spent, limit=acc.daily_limit)
            if acc.monthly_limit >= 0 and acc.monthly_spent + amount > acc.monthly_limit:
                raise MonthlyTokenLimitError(
                    used=acc.monthly_spent, limit=acc.monthly_limit
                )

            acc.daily_spent += amount
            acc.monthly_spent += amount
            store.account_set(acc)
            store.apply_delta(
                user_id=user_id,
                delta=-amount,
                kind="debit",
                reason=reason,
                request_id=request_id,
                actor_id=None,
                account=acc,
            )
            store.charge_set(
                ChargeRecord(
                    request_id=request_id,
                    user_id=user_id,
                    amount=amount,
                    status="charged",
                    reason=reason,
                )
            )
            return store.account_get(user_id) or acc

        return self._store.run_atomic(_op)

    def refund(
        self, request_id: str, *, user_id: str, reason: str = "ai_error_refund"
    ) -> TokenAccount | None:
        """Refund a prior charge. Idempotent if already refunded / unknown."""

        def _op(store: TokenStore) -> TokenAccount | None:
            charge = store.charge_get(request_id, user_id)
            if charge is None:
                return None
            if charge.status == "refunded":
                return store.account_get(charge.user_id)

            acc = store.account_get(charge.user_id)
            if acc is None:
                acc = self._new_account(charge.user_id)
                store.account_set(acc)
            acc = self._refresh_periods(store, acc)
            # Roll back period spenders when still in same period
            acc.daily_spent = max(0, acc.daily_spent - charge.amount)
            acc.monthly_spent = max(0, acc.monthly_spent - charge.amount)
            store.account_set(acc)
            store.apply_delta(
                user_id=charge.user_id,
                delta=charge.amount,
                kind="refund",
                reason=reason,
                request_id=request_id,
                actor_id="system",
                account=acc,
            )
            charge.status = "refunded"
            charge.refunded_at = utcnow()
            store.charge_set(charge)
            return store.account_get(charge.user_id)

        return self._store.run_atomic(_op)

    @contextmanager
    def charge_for_ai(
        self,
        user_id: str,
        amount: int,
        *,
        request_id: str,
        reason: str = "ai_request",
    ) -> Iterator[TokenAccount]:
        """Debit before AI work; auto-refund on any exception."""
        account = self.charge(
            user_id, amount, request_id=request_id, reason=reason
        )
        try:
            yield account
        except Exception:
            self.refund(request_id, user_id=user_id, reason="ai_error_refund")
            raise

    # --- admin ---------------------------------------------------------------
    def admin_credit(
        self,
        user_id: str,
        amount: int,
        *,
        actor_id: str,
        reason: str = "admin_credit",
    ) -> TokenAccount:
        if amount <= 0:
            raise InvalidTokenAmountError()

        def _op(store: TokenStore) -> TokenAccount:
            acc = store.account_get(user_id) or self._new_account(user_id)
            if store.account_get(user_id) is None:
                store.account_set(acc)
            acc = self._refresh_periods(store, acc)
            store.apply_delta(
                user_id=user_id,
                delta=amount,
                kind="admin_credit",
                reason=reason,
                request_id=None,
                actor_id=actor_id,
                account=acc,
            )
            return store.account_get(user_id) or acc

        return self._store.run_atomic(_op)

    def admin_debit(
        self,
        user_id: str,
        amount: int,
        *,
        actor_id: str,
        reason: str = "admin_debit",
    ) -> TokenAccount:
        if amount <= 0:
            raise InvalidTokenAmountError()

        def _op(store: TokenStore) -> TokenAccount:
            acc = store.account_get(user_id) or self._new_account(user_id)
            if store.account_get(user_id) is None:
                store.account_set(acc)
            acc = self._refresh_periods(store, acc)
            if acc.balance < amount:
                raise InsufficientTokensError(balance=acc.balance, required=amount)
            store.apply_delta(
                user_id=user_id,
                delta=-amount,
                kind="admin_debit",
                reason=reason,
                request_id=None,
                actor_id=actor_id,
                account=acc,
            )
            return store.account_get(user_id) or acc

        return self._store.run_atomic(_op)

    def admin_set_limits(
        self,
        user_id: str,
        *,
        daily_limit: int | None = None,
        monthly_limit: int | None = None,
        actor_id: str,
    ) -> TokenAccount:
        def _op(store: TokenStore) -> TokenAccount:
            acc = store.account_get(user_id) or self._new_account(user_id)
            if daily_limit is not None:
                if daily_limit < 0:
                    raise InvalidTokenAmountError("daily_limit must be >= 0")
                acc.daily_limit = daily_limit
            if monthly_limit is not None:
                if monthly_limit < 0:
                    raise InvalidTokenAmountError("monthly_limit must be >= 0")
                acc.monthly_limit = monthly_limit
            acc.updated_at = utcnow()
            store.account_set(acc)
            # audit trail (zero-amount ledger via credit 0 is weird — use reason note)
            store.apply_delta(
                user_id=user_id,
                delta=0,
                kind="admin_credit",
                reason=(
                    f"admin_set_limits daily={acc.daily_limit} "
                    f"monthly={acc.monthly_limit}"
                ),
                request_id=None,
                actor_id=actor_id,
                account=acc,
            )
            return store.account_get(user_id) or acc

        return self._store.run_atomic(_op)

    # --- helpers -------------------------------------------------------------
    def _new_account(self, user_id: str) -> TokenAccount:
        return TokenAccount(
            user_id=user_id,
            balance=0,
            daily_limit=self._default_daily,
            monthly_limit=self._default_monthly,
            daily_period=_day_key(),
            monthly_period=_month_key(),
        )

    def _bootstrap_account(self, store: TokenStore, user_id: str) -> TokenAccount:
        """Create account at balance 0, then credit initial grant once (ledgered)."""
        acc = self._new_account(user_id)
        store.account_set(acc)
        if self._default_balance > 0:
            store.apply_delta(
                user_id=user_id,
                delta=self._default_balance,
                kind="credit",
                reason="initial_grant",
                request_id=None,
                actor_id="system",
                account=acc,
            )
            return store.account_get(user_id) or acc
        return acc

    def _refresh_periods(self, store: TokenStore, acc: TokenAccount) -> TokenAccount:
        day = _day_key()
        month = _month_key()
        changed = False
        if acc.daily_period != day:
            acc.daily_period = day
            acc.daily_spent = 0
            changed = True
        if acc.monthly_period != month:
            acc.monthly_period = month
            acc.monthly_spent = 0
            changed = True
        if changed:
            store.account_set(acc)
        return acc
