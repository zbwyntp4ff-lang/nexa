"""Filesystem sandboxing for ``FileRead``/``FileWrite``/``DirectoryList``.
All three tools resolve user-supplied paths through :func:`resolve_safe_path`,
which guarantees the resulting path can never escape the configured sandbox
root - protecting against ``../`` path traversal, absolute-path escapes, and
symlink-based escapes.
"""
from __future__ import annotations
from pathlib import Path
from app.models.errors import PathTraversalError
def resolve_safe_path(sandbox_root: Path, user_path: str) -> Path:
    """Resolve ``user_path`` (relative or absolute) against ``sandbox_root``.
    Raises:
        app.models.errors.PathTraversalError: If the resolved path would
            fall outside of ``sandbox_root``, or if ``user_path`` contains a
            NUL byte.
    """
    if "\x00" in user_path:
        raise PathTraversalError(user_path)
    root = sandbox_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    candidate = Path(user_path)
    # Treat absolute paths as *relative to the sandbox root* rather than the
    # real filesystem root - "/etc/passwd" becomes "<root>/etc/passwd", never
    # the real /etc/passwd. This mirrors how most sandboxed file tools behave.
    if candidate.is_absolute():
        candidate = Path(*candidate.parts[1:])
    combined = (root / candidate)
    # Resolve without requiring the path to exist, but still normalize ".."
    # segments so traversal attempts are caught before touching the disk.
    resolved = _resolve_without_requiring_existence(combined)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError(user_path) from exc
    return resolved
def _resolve_without_requiring_existence(path: Path) -> Path:
    """Normalize ``..``/``.`` segments in ``path`` without requiring it to exist.
    ``Path.resolve()`` on a missing path still works on modern Python, but we
    implement this manually to also work predictably for paths whose parents
    don't exist yet (e.g. before ``FileWrite`` creates them).
    """
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part in (".", ""):
            continue
        else:
            parts.append(part)
    if not parts:
        return Path(path.anchor or "/")
    return Path(parts[0]) / Path(*parts[1:]) if len(parts) > 1 else Path(parts[0])
