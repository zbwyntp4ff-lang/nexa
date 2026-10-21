"""Load OAuth client files dropped into data/oauth/ (Google Cloud JSON, etc.)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def oauth_dir(settings: Any) -> Path:
    raw = getattr(settings, "oauth_credentials_dir", None) or "data/oauth"
    return Path(str(raw))


def _pair_from_mapping(data: dict[str, Any]) -> tuple[str, str] | None:
    nested = data.get("web") or data.get("installed") or data.get("google")
    if isinstance(nested, dict):
        data = nested
    client_id = str(data.get("client_id") or data.get("clientId") or "").strip()
    client_secret = str(data.get("client_secret") or data.get("clientSecret") or "").strip()
    if client_id and client_secret:
        return client_id, client_secret
    return None


def load_google_oauth(settings: Any) -> tuple[str, str] | None:
    env_id = (getattr(settings, "oauth_google_client_id", None) or "").strip()
    env_secret = (getattr(settings, "oauth_google_client_secret", None) or "").strip()
    if env_id and env_secret:
        return env_id, env_secret
    folder = oauth_dir(settings)
    candidates = [
        folder / "google.json",
        folder / "client_secret.json",
        folder / "client_secrets.json",
    ]
    if folder.is_dir():
        candidates.extend(sorted(folder.glob("client_secret*.json")))
    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict):
            pair = _pair_from_mapping(data)
            if pair:
                return pair
    return None


def save_google_oauth(settings: Any, client_id: str, client_secret: str) -> Path:
    folder = oauth_dir(settings)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "google.json"
    payload = {
        "web": {
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
