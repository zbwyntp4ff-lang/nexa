"""Filesystem sandboxing for agent workspace tools.

Paths are resolved by the operating system (including symlinks) before the
containment check. Authenticated cloud users receive separate workspace roots.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.models.errors import PathTraversalError

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def user_workspace_root(sandbox_root: Path, user_id: str | None) -> Path:
    """Return an isolated workspace for an authenticated user.

    Unauthenticated local desktop mode keeps the legacy workspace for backwards
    compatibility. Public/multi-user requests are authenticated upstream and
    are assigned a per-user directory beneath the configured workspace root.
    """
    if user_id is None:
        return sandbox_root
    uid = str(user_id).strip()
    if not _USER_ID_RE.fullmatch(uid):
        raise PathTraversalError("invalid user workspace identifier")
    root = sandbox_root.resolve()
    scoped = root / "users" / uid
    scoped.mkdir(parents=True, exist_ok=True)
    resolved = scoped.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError("user workspace escapes configured root") from exc
    return resolved


def resolve_safe_path(sandbox_root: Path, user_path: str) -> Path:
    """Resolve a user path and reject traversal or symlink escapes."""
    if "\x00" in user_path:
        raise PathTraversalError(user_path)
    root = sandbox_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    candidate = Path(user_path)
    # Absolute paths are interpreted relative to the sandbox, never the OS root.
    if candidate.is_absolute():
        candidate = Path(*candidate.parts[1:])
    combined = root / candidate
    # Resolve existing symlinks, including symlinked parent directories, while
    # still supporting destinations that have not been created yet.
    resolved = combined.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError(user_path) from exc
    return resolved
