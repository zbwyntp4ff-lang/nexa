"""Thread- and process-safe JSON persistence for token accounts / ledger.

Atomic updates use:
1. ``threading.RLock`` for in-process concurrency
2. Exclusive file lock on ``*.lock`` for multi-process safety
3. Reload-from-disk inside the critical section before mutate
4. Write to ``*.tmp`` then ``os.replace`` for durable swap
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TypeVar

from app.tokens.errors import NegativeBalanceError
from app.tokens.models import ChargeRecord, LedgerEntry, TokenAccount, utcnow

T = TypeVar("T")


class TokenStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._lock = threading.RLock()
        self._accounts: dict[str, TokenAccount] = {}
        self._ledger: list[LedgerEntry] = []
        self._charges: dict[str, ChargeRecord] = {}
        self._load()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Hold process + OS file lock; reload state before critical section."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._lock_path, "a+", encoding="utf-8") as lock_file:
                self._acquire_file_lock(lock_file)
                try:
                    self._load()
                    yield
                    self._flush()
                finally:
                    self._release_file_lock(lock_file)

    def run_atomic(self, fn: Callable[[TokenStore], T]) -> T:
        with self.exclusive():
            return fn(self)

    @staticmethod
    def _acquire_file_lock(lock_file) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                if lock_file.read(1) == "":
                    lock_file.write("0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise RuntimeError(
                f"Cannot acquire NEXA token-store lock at {lock_file.name}: {exc}"
            ) from exc

    @staticmethod
    def _release_file_lock(lock_file) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

    def _load(self) -> None:
        self._accounts = {}
        self._ledger = []
        self._charges = {}
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # Never turn an unreadable token ledger into an empty account store:
            # the next write could permanently erase balances and charge history.
            raise RuntimeError(
                f"Cannot load NEXA token store at {self._path}: {exc}"
            ) from exc
        for entry in raw.get("accounts", []):
            item = TokenAccount.model_validate(entry)
            self._accounts[item.user_id] = item
        for entry in raw.get("ledger", []):
            self._ledger.append(LedgerEntry.model_validate(entry))
        for entry in raw.get("charges", []):
            item = ChargeRecord.model_validate(entry)
            self._charges[item.request_id] = item

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "accounts": [a.model_dump(mode="json") for a in self._accounts.values()],
            "ledger": [e.model_dump(mode="json") for e in self._ledger],
            "charges": [c.model_dump(mode="json") for c in self._charges.values()],
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)

    def account_get(self, user_id: str) -> TokenAccount | None:
        acc = self._accounts.get(user_id)
        return acc.model_copy(deep=True) if acc else None

    def account_set(self, account: TokenAccount) -> None:
        if account.balance < 0:
            raise NegativeBalanceError()
        self._accounts[account.user_id] = account

    def charge_get(self, request_id: str) -> ChargeRecord | None:
        c = self._charges.get(request_id)
        return c.model_copy(deep=True) if c else None

    def charge_set(self, charge: ChargeRecord) -> None:
        self._charges[charge.request_id] = charge

    def ledger_append(self, entry: LedgerEntry) -> None:
        self._ledger.append(entry)

    def ledger_list(
        self, *, user_id: str | None, limit: int, offset: int
    ) -> list[LedgerEntry]:
        items = self._ledger
        if user_id is not None:
            items = [e for e in items if e.user_id == user_id]
        ordered = list(reversed(items))
        return [e.model_copy(deep=True) for e in ordered[offset : offset + max(0, limit)]]

    def delete_user(self, user_id: str) -> None:
        """Remove account + ledger/charge rows for ``user_id`` (account wipe)."""

        def _op(store: TokenStore) -> None:
            store._accounts.pop(user_id, None)
            store._ledger = [e for e in store._ledger if e.user_id != user_id]
            store._charges = {
                rid: c
                for rid, c in store._charges.items()
                if getattr(c, "user_id", None) != user_id
            }

        self.run_atomic(_op)

    def apply_delta(
        self,
        *,
        user_id: str,
        delta: int,
        kind: str,
        reason: str,
        request_id: str | None,
        actor_id: str | None,
        account: TokenAccount,
    ) -> tuple[TokenAccount, LedgerEntry]:
        before = account.balance
        after = before + delta
        if after < 0:
            raise NegativeBalanceError(
                f"Refusing balance {before} + ({delta}) -> {after}."
            )
        entry = LedgerEntry(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=delta,
            kind=kind,  # type: ignore[arg-type]
            reason=reason,
            balance_before=before,
            balance_after=after,
            request_id=request_id,
            actor_id=actor_id,
            created_at=utcnow(),
        )
        account.balance = after
        account.updated_at = utcnow()
        self.account_set(account)
        self.ledger_append(entry)
        return account.model_copy(deep=True), entry.model_copy(deep=True)
