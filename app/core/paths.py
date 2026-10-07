"""Project-root-relative path resolution helpers.
Used so that relative configuration values (e.g. ``AGENT_WORKSPACE_DIR`` or
``MEMORY_STORE_PATH``) behave consistently regardless of the process's
current working directory.
"""
from __future__ import annotations
from pathlib import Path
# app/core/paths.py -> app/core -> app -> <project root>
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
def resolve_under_project_root(path_str: str) -> Path:
    """Resolve ``path_str`` against :data:`PROJECT_ROOT` if it is relative."""
    path = Path(path_str)
    return path if path.is_absolute() else (PROJECT_ROOT / path)
