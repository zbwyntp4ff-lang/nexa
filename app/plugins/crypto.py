"""Authenticated encryption for plugin secrets.

New writes use AES-256-GCM. NEXA1 blobs remain readable for an in-place
migration; they are never emitted again.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.paths import PROJECT_ROOT, resolve_under_project_root

_MAGIC = b"NEXA2"
_LEGACY_MAGIC = b"NEXA1"
_LEGACY_ITERATIONS = 120_000
_AES_GCM_NONCE_BYTES = 12


def load_or_create_master_key(key_path: str) -> bytes:
    """Return a 32-byte master key, creating it atomically with owner-only mode."""
    path = resolve_under_project_root(key_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if not path.is_file():
            raise RuntimeError(f"NEXA plugin key path is not a regular file: {path}")
        data = path.read_bytes()
        if len(data) < 32:
            # Replacing a damaged key would make all existing encrypted secrets
            # unrecoverable. Fail closed and require an operator recovery.
            raise RuntimeError(f"NEXA plugin master key is corrupt or truncated: {path}")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return data[:32]

    key = os.urandom(32)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Another worker created the key first; use the winning key.
        data = path.read_bytes()
        if len(data) < 32:
            raise RuntimeError(f"NEXA plugin master key is corrupt or truncated: {path}")
        return data[:32]
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
        handle.flush()
        os.fsync(handle.fileno())
    return key


def encrypt_secret(plaintext: str, master_key: bytes) -> str:
    """Encrypt with AES-256-GCM and bind the format marker as associated data."""
    if len(master_key) != 32:
        raise ValueError("Plugin master key must be exactly 32 bytes.")
    nonce = os.urandom(_AES_GCM_NONCE_BYTES)
    ciphertext = AESGCM(master_key).encrypt(
        nonce, plaintext.encode("utf-8"), _MAGIC
    )
    blob = _MAGIC + nonce + ciphertext
    return base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt_secret(token: str, master_key: bytes) -> str:
    """Decrypt NEXA2 AES-GCM or read-only legacy NEXA1 encrypted values."""
    try:
        blob = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid secret encoding") from exc

    if blob.startswith(_MAGIC):
        if len(blob) < len(_MAGIC) + _AES_GCM_NONCE_BYTES + 16:
            raise ValueError("Invalid secret payload")
        if len(master_key) != 32:
            raise ValueError("Plugin master key must be exactly 32 bytes.")
        nonce_start = len(_MAGIC)
        nonce = blob[nonce_start:nonce_start + _AES_GCM_NONCE_BYTES]
        ciphertext = blob[nonce_start + _AES_GCM_NONCE_BYTES:]
        try:
            plaintext = AESGCM(master_key).decrypt(nonce, ciphertext, _MAGIC)
        except (InvalidTag, ValueError) as exc:
            raise ValueError("Secret authentication failed") from exc
        return plaintext.decode("utf-8")

    if blob.startswith(_LEGACY_MAGIC):
        return _decrypt_legacy(blob, master_key)

    raise ValueError("Invalid secret payload")


def _decrypt_legacy(blob: bytes, master_key: bytes) -> str:
    """Read-only compatibility for secrets encrypted by the former NEXA1 format."""
    header_size = len(_LEGACY_MAGIC) + 16 + 16 + 32
    if len(blob) < header_size:
        raise ValueError("Invalid legacy secret payload")
    salt_start = len(_LEGACY_MAGIC)
    salt = blob[salt_start:salt_start + 16]
    nonce = blob[salt_start + 16:salt_start + 32]
    mac = blob[salt_start + 32:salt_start + 64]
    ciphertext = blob[salt_start + 64:]
    key = hashlib.pbkdf2_hmac(
        "sha256", master_key, salt, _LEGACY_ITERATIONS, dklen=32
    )
    expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("Legacy secret authentication failed")
    stream = _legacy_keystream(key, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream, strict=True))
    return plaintext.decode("utf-8")


def _legacy_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(out[:length])


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "••••"
    return value[:4] + "…" + value[-2:]


def default_key_path() -> str:
    return str((PROJECT_ROOT / "data" / "plugin.key").as_posix())
