"""Path allowlisting with symlink-escape protection."""
from __future__ import annotations

import os
from pathlib import Path

from app.models.errors import PathTraversalError


def allowed_roots(sandbox_root: Path, extra: list[str] | None = None) -> list[Path]:
    roots = [sandbox_root.resolve()]
    for raw in extra or []:
        if not raw or not str(raw).strip():
            continue
        try:
            roots.append(Path(raw).expanduser().resolve())
        except OSError:
            continue
    return roots


def resolve_allowed_path(
    user_path: str,
    *,
    roots: list[Path],
    must_exist: bool = False,
) -> Path:
    """Resolve ``user_path`` under one of ``roots``; block traversal/symlink escapes."""
    if not user_path or not isinstance(user_path, str) or "\x00" in user_path:
        raise PathTraversalError(user_path or "")
    raw = Path(user_path).expanduser()
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        for root in roots:
            candidates.append(root / raw)

    last_err: Exception | None = None
    for candidate in candidates:
        try:
            # Resolve symlinks so escapes via link cannot leave the root.
            resolved = candidate.resolve(strict=must_exist)
        except (OSError, RuntimeError) as exc:
            last_err = exc
            continue
        for root in roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
    raise PathTraversalError(user_path) from last_err


def is_under_roots(path: Path, roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def env_extra_roots() -> list[str]:
    raw = os.environ.get("NEXA_DESKTOP_ALLOWED_DIRS") or ""
    if not raw.strip():
        return []
    return [p.strip() for p in raw.split(os.pathsep) if p.strip()]
