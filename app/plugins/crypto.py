"""Encrypt plugin secrets at rest (stdlib only — no extra dependency)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from app.core.paths import PROJECT_ROOT, resolve_under_project_root

_MAGIC = b"NEXA1"
_ITERATIONS = 120_000


def load_or_create_master_key(key_path: str) -> bytes:
    """Return a 32-byte master key, creating it on disk if missing."""
    path = resolve_under_project_root(key_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        data = path.read_bytes()
        if len(data) >= 32:
            return data[:32]
    key = os.urandom(32)
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def encrypt_secret(plaintext: str, master_key: bytes) -> str:
    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", master_key, salt, _ITERATIONS, dklen=32)
    data = plaintext.encode("utf-8")
    stream = _keystream(key, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, stream, strict=True))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    blob = _MAGIC + salt + nonce + mac + ct
    return base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt_secret(token: str, master_key: bytes) -> str:
    try:
        blob = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid secret encoding") from exc
    if len(blob) < 5 + 16 + 16 + 32 or not blob.startswith(_MAGIC):
        raise ValueError("Invalid secret payload")
    salt = blob[5:21]
    nonce = blob[21:37]
    mac = blob[37:69]
    ct = blob[69:]
    key = hashlib.pbkdf2_hmac("sha256", master_key, salt, _ITERATIONS, dklen=32)
    expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("Secret MAC mismatch")
    stream = _keystream(key, nonce, len(ct))
    data = bytes(a ^ b for a, b in zip(ct, stream, strict=True))
    return data.decode("utf-8")


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "••••"
    return value[:4] + "…" + value[-2:]


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(out[:length])


def default_key_path() -> str:
    return str((PROJECT_ROOT / "data" / "plugin.key").as_posix())
