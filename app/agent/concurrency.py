"""Per-user agent concurrency caps for open beta (in-process)."""
from __future__ import annotations

import asyncio

from app.config.settings import get_settings
from app.models.errors import NexaError


class AgentBusyError(NexaError):
    """User already has the maximum number of agent runs in flight."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "Too many agent tasks in progress. Wait for the current run to finish."
        )


_locks: dict[str, asyncio.Semaphore] = {}
_meta_lock = asyncio.Lock()


async def try_acquire_agent_slot(user_id: str | None) -> asyncio.Semaphore | None:
    """Non-blocking per-user slot. ``None`` means unlimited / anonymous."""
    settings = get_settings()
    limit = int(getattr(settings, "agent_max_parallel_per_user", 0) or 0)
    if limit <= 0 or not user_id:
        return None
    async with _meta_lock:
        sem = _locks.get(user_id)
        if sem is None:
            sem = asyncio.Semaphore(limit)
            _locks[user_id] = sem
    if sem.locked():
        raise AgentBusyError()
    await sem.acquire()
    return sem


def release_agent_slot(sem: asyncio.Semaphore | None) -> None:
    if sem is not None:
        sem.release()


def reset_agent_concurrency() -> None:
    """Test helper."""
    _locks.clear()
