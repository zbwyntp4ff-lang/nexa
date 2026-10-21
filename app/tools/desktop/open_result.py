"""Open a generated result file with the OS default application (local only)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.tools.base import Tool, ToolResult
from app.tools.desktop.locality import require_local_desktop
from app.tools.desktop.paths import allowed_roots, env_extra_roots, resolve_allowed_path
from app.tools.office.result_store import ResultStore


class OpenResultTool(Tool):
    name = "open_result"
    description = (
        "Open a generated result (by file_id) or an allowlisted path with the OS default app. "
        "Local desktop only. Does not claim PowerPoint/Word are installed — reports what was attempted."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_id": {"type": "string"},
            "path": {"type": "string"},
            "confirm": {"type": "boolean"},
        },
        "required": [],
    }
    permissions = frozenset({"filesystem:read"})

    def __init__(self, sandbox_root: Path, store: ResultStore | None = None) -> None:
        self._sandbox_root = sandbox_root.resolve()
        self._store = store
        self._extra = env_extra_roots()

    async def execute(self, **kwargs: Any) -> ToolResult:
        blocked = require_local_desktop("open_result")
        if blocked:
            return ToolResult(success=False, error=blocked, metadata={"status": "remote_refused"})

        if not bool(kwargs.get("confirm")):
            return ToolResult(
                success=False,
                error="Opening a file in an external app requires confirm=true after user approval.",
                metadata={"needs_confirmation": True, "action": "open_result"},
            )

        file_id = kwargs.get("file_id")
        path_raw = kwargs.get("path")
        target: Path | None = None
        filename = None

        if file_id and isinstance(file_id, str):
            if self._store is None:
                return ToolResult(success=False, error="Result store unavailable.")
            # Same ACL as Results HTTP API — never open via absolute_path alone.
            uid = kwargs.get("user_id")
            uid_s = uid.strip() if isinstance(uid, str) and uid.strip() else None
            rec = self._store.get(file_id, user_id=uid_s)
            if rec is None:
                return ToolResult(
                    success=False,
                    error="file_id not found or access denied.",
                    metadata={"status": "acl_denied"},
                )
            target = self._store.absolute_path(file_id)
            filename = rec.filename
            if target is None:
                return ToolResult(success=False, error="file_id not found.")
        elif path_raw and isinstance(path_raw, str):
            try:
                target = resolve_allowed_path(
                    path_raw,
                    roots=allowed_roots(self._sandbox_root, self._extra),
                    must_exist=True,
                )
            except Exception as exc:  # noqa: BLE001
                return ToolResult(success=False, error=str(exc), metadata={"status": "path_denied"})
            filename = target.name
        else:
            return ToolResult(success=False, error="Provide file_id or path.")

        probe = probe_default_handlers(target.suffix)
        try:
            opened = open_with_default_app(target)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"Failed to open file: {exc.__class__.__name__}",
                metadata={"status": "open_failed", "handlers": probe},
            )
        return ToolResult(
            success=True,
            output={
                "opened": opened,
                "filename": filename,
                "suffix": target.suffix.lower(),
                "handlers_detected": probe,
                "note": (
                    "Requested OS default handler. "
                    "This does not prove a specific app (e.g. PowerPoint) is installed "
                    "unless listed under handlers_detected."
                ),
            },
            metadata={"status": "ok"},
        )


def probe_default_handlers(suffix: str) -> dict[str, Any]:
    """Best-effort detection — never invent installed apps."""
    suffix = (suffix or "").lower()
    found: dict[str, Any] = {"platform": sys.platform, "candidates": []}
    if sys.platform == "win32":
        candidates = []
        if suffix == ".pptx":
            candidates = [
                Path(r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"),
                Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE"),
            ]
            which = shutil.which("POWERPNT.EXE")
            if which:
                candidates.append(Path(which))
        elif suffix == ".docx":
            candidates = [
                Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"),
            ]
            which = shutil.which("WINWORD.EXE")
            if which:
                candidates.append(Path(which))
        elif suffix == ".xlsx":
            candidates = [
                Path(r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"),
            ]
            which = shutil.which("EXCEL.EXE")
            if which:
                candidates.append(Path(which))
        existing = [str(p) for p in candidates if p and p.is_file()]
        found["candidates"] = existing
        found["likely_office_app"] = bool(existing)
    else:
        found["candidates"] = []
        found["likely_office_app"] = None
        found["note"] = "Non-Windows: will use xdg-open/open without claiming a specific suite."
    return found


def open_with_default_app(path: Path) -> bool:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return True
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False, timeout=15)
        return True
    subprocess.run(["xdg-open", str(path)], check=False, timeout=15)
    return True
