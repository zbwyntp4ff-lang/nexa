"""JSON persistence for user profiles (one record per user_id)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from app.profile.models import UserProfile


class ProfileStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._profiles: dict[str, UserProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # An empty profile map would overwrite the only copy of user
            # preferences on the next update; fail startup instead.
            raise RuntimeError(
                f"Cannot load NEXA profile store at {self._path}: {exc}"
            ) from exc
        for entry in raw.get("profiles", []):
            try:
                profile = UserProfile.model_validate(entry)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    f"Invalid profile record in NEXA profile store at {self._path}: {exc}"
                ) from exc
            self._profiles[profile.user_id] = profile

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "profiles": [p.model_dump(mode="json") for p in self._profiles.values()],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    def get(self, user_id: str) -> UserProfile | None:
        with self._lock:
            return self._profiles.get(user_id)

    def save(self, profile: UserProfile) -> UserProfile:
        with self._lock:
            self._profiles[profile.user_id] = profile
            self._flush()
        return profile

    def delete(self, user_id: str) -> bool:
        with self._lock:
            existed = self._profiles.pop(user_id, None) is not None
            if existed:
                self._flush()
            return existed
