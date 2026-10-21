"""Path sandbox for plugin workspaces — reuse Tool sandbox semantics."""
from __future__ import annotations

from pathlib import Path

from app.tools.sandbox import resolve_safe_path


def plugin_root(workspace_dir: Path, plugin_id: str) -> Path:
    root = (workspace_dir / plugin_id).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_in_plugin(workspace_dir: Path, plugin_id: str, user_path: str) -> Path:
    return resolve_safe_path(plugin_root(workspace_dir, plugin_id), user_path)
