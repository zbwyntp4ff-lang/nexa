"""Shared sandboxed file ops with diff + undo for local adapters."""
from __future__ import annotations

import difflib
import json
import time
from pathlib import Path
from typing import Any

from app.plugins.paths import plugin_root, resolve_in_plugin


class FileWorkspace:
    def __init__(self, workspace_dir: Path, plugin_id: str, max_bytes: int = 1_000_000) -> None:
        self.root = plugin_root(workspace_dir, plugin_id)
        self.plugin_id = plugin_id
        self.max_bytes = max_bytes
        self._undo = self.root / ".nexa-undo"
        self._undo.mkdir(parents=True, exist_ok=True)

    def list_tree(self, rel: str = ".", max_entries: int = 400) -> list[dict[str, Any]]:
        base = resolve_in_plugin(self.root.parent, self.plugin_id, rel)
        if not base.exists():
            return []
        out: list[dict[str, Any]] = []
        if base.is_file():
            return [{"path": self._rel(base), "kind": "file", "size": base.stat().st_size}]
        for path in sorted(base.rglob("*")):
            if ".nexa-undo" in path.parts:
                continue
            kind = "dir" if path.is_dir() else "file"
            item: dict[str, Any] = {"path": self._rel(path), "kind": kind}
            if kind == "file":
                item["size"] = path.stat().st_size
            out.append(item)
            if len(out) >= max_entries:
                break
        return out

    def read_text(self, rel: str) -> str:
        path = resolve_in_plugin(self.root.parent, self.plugin_id, rel)
        if not path.is_file():
            raise FileNotFoundError(rel)
        data = path.read_bytes()
        if len(data) > self.max_bytes:
            raise ValueError(f"File exceeds {self.max_bytes} bytes")
        return data.decode("utf-8")

    def preview_write(self, rel: str, content: str) -> dict[str, Any]:
        path = resolve_in_plugin(self.root.parent, self.plugin_id, rel)
        old = ""
        exists = path.is_file()
        if exists:
            old = path.read_text(encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
        return {"path": rel, "exists": exists, "diff": diff or "(no changes)"}

    def apply_write(self, rel: str, content: str) -> dict[str, Any]:
        path = resolve_in_plugin(self.root.parent, self.plugin_id, rel)
        previous = None
        if path.is_file():
            previous = path.read_text(encoding="utf-8")
        self._push_undo(rel, previous)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"path": rel, "bytes": len(content.encode("utf-8")), "overwrote": previous is not None}

    def undo_last(self) -> dict[str, Any]:
        log = self._undo / "log.json"
        if not log.is_file():
            return {"undone": False, "reason": "nothing to undo"}
        items = json.loads(log.read_text(encoding="utf-8"))
        if not items:
            return {"undone": False, "reason": "nothing to undo"}
        last = items.pop()
        rel = last["path"]
        path = resolve_in_plugin(self.root.parent, self.plugin_id, rel)
        prev = last.get("previous")
        if prev is None:
            if path.is_file():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prev, encoding="utf-8")
        log.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return {"undone": True, "path": rel}

    def _push_undo(self, rel: str, previous: str | None) -> None:
        log = self._undo / "log.json"
        items: list[dict[str, Any]] = []
        if log.is_file():
            try:
                items = json.loads(log.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                items = []
        items.append({"path": rel, "previous": previous, "at": time.time()})
        log.write_text(json.dumps(items[-50:], ensure_ascii=False), encoding="utf-8")

    def _rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.name
