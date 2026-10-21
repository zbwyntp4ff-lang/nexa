"""Detect whether this backend process may safely touch the host OS.

Remote/cloud backends must never open files or launch apps on an operator
machine they do not control. Electron sets ``NEXA_LOCAL_DESKTOP=1`` when it
spawns the local backend.
"""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache
def is_local_desktop() -> bool:
    """True only when ``NEXA_LOCAL_DESKTOP`` is explicitly enabled.

    Development heuristics were removed for closed-beta safety: a mis-tagged
    remote host must not gain OS tools. Tests and Electron must set the flag.
    """
    flag = (os.environ.get("NEXA_LOCAL_DESKTOP") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def require_local_desktop(action: str) -> str | None:
    """Return an error message if OS action is not allowed; else None."""
    if is_local_desktop():
        return None
    return (
        f"Refused '{action}': this backend is not marked as a local desktop "
        "(set NEXA_LOCAL_DESKTOP=1 only on the user's machine / Electron). "
        "Remote servers cannot control the user's OS."
    )


def clear_locality_cache() -> None:
    is_local_desktop.cache_clear()
