"""REALITY CHECK — READY only after real files + tests + preview path resolve."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.build import store


@dataclass
class RealityCheckResult:
    ok: bool
    reasons: list[str]

    @property
    def detail(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "ok"


def reality_check_ready(
    *,
    project_id: str,
    root_rel: str,
    entry_file: str,
    expected_files: list[str],
    tests_passed: bool,
    preview_url: str | None,
) -> RealityCheckResult:
    """Gate for READY — never hardcode success."""
    reasons: list[str] = []

    if not project_id:
        reasons.append("missing project_id")
    if not root_rel:
        reasons.append("missing workspace root_rel")
    if not tests_passed:
        reasons.append("tests not passed")
    if not preview_url or "/api/v1/build/preview/" not in preview_url:
        reasons.append("preview url missing or invalid")

    ws = store.workspace_root().resolve()
    root = (ws / root_rel).resolve()
    try:
        root.relative_to(ws)
    except ValueError:
        reasons.append("project root escapes workspace")
        return RealityCheckResult(ok=False, reasons=reasons)

    if not root.is_dir():
        reasons.append(f"project directory missing: {root}")
    else:
        for name in expected_files:
            clean = name.replace("\\", "/").lstrip("/")
            if ".." in clean.split("/"):
                reasons.append(f"unsafe file path: {name}")
                continue
            path = (root / clean).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                reasons.append(f"file path escapes project: {name}")
                continue
            if not path.is_file():
                reasons.append(f"file missing on disk: {name}")

    entry = (root / entry_file).resolve()
    try:
        entry.relative_to(root)
    except ValueError:
        reasons.append("entry escapes project root")
    else:
        if not entry.is_file():
            reasons.append(f"entry missing: {entry_file}")
        else:
            try:
                text = entry.read_text(encoding="utf-8")
            except OSError as exc:
                reasons.append(f"entry unreadable: {exc}")
            else:
                if "<html" not in text.lower():
                    reasons.append("entry is not HTML")

    return RealityCheckResult(ok=not reasons, reasons=reasons)


def assert_path_inside_workspace(path: Path) -> bool:
    try:
        path.resolve().relative_to(store.workspace_root().resolve())
        return True
    except ValueError:
        return False
