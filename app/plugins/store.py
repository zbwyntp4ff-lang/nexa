"""Persist plugin connection state. Secrets are encrypted blobs, never plaintext.

Multi-tenant: states are keyed by ``(user_id, plugin_id)``.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from app.plugins.models import PluginState


def _key(user_id: str | None, plugin_id: str) -> str:
    return f"{user_id or '_'}::{plugin_id}"


class PluginStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._states: dict[str, PluginState] = {}
        self._load()

    def get(self, plugin_id: str, *, user_id: str | None = None) -> PluginState | None:
        with self._lock:
            state = self._states.get(_key(user_id, plugin_id))
            return state.model_copy(deep=True) if state else None

    def upsert(self, state: PluginState) -> None:
        with self._lock:
            self._states[_key(state.user_id, state.plugin_id)] = state.model_copy(deep=True)
            self._flush()

    def all(self, *, user_id: str | None = None) -> list[PluginState]:
        with self._lock:
            items = [s.model_copy(deep=True) for s in self._states.values()]
        if user_id is not None:
            items = [s for s in items if s.user_id == user_id]
        return items

    def delete_user(self, user_id: str) -> int:
        with self._lock:
            to_remove = [k for k, s in self._states.items() if s.user_id == user_id]
            for key in to_remove:
                del self._states[key]
            if to_remove:
                self._flush()
            return len(to_remove)

    def _load(self) -> None:
        if not self._path.exists():
            self._states = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("plugins"), list):
                raise ValueError("plugin store must contain a 'plugins' list")
            out: dict[str, PluginState] = {}
            for index, item in enumerate(raw["plugins"]):
                try:
                    state = PluginState.model_validate(item)
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid plugin entry at index {index}: {exc}") from exc
                out[_key(state.user_id, state.plugin_id)] = state
        except Exception as exc:  # noqa: BLE001
            # Never turn a corrupt credential store into an empty one; a later
            # save would overwrite the only copy of encrypted plugin secrets.
            raise RuntimeError(f"Cannot load NEXA plugin store at {self._path}: {exc}") from exc
        self._states = out

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"plugins": [s.model_dump() for s in self._states.values()]}
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
