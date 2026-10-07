"""Password hashing helpers (stdlib scrypt — no extra dependency)."""
from __future__ import annotations

import hashlib
import hmac
import secrets


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 64


def hash_password(password: str) -> str:
    """Return a portable ``scrypt$…`` hash string for ``password``."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of ``password`` against a stored hash."""
    try:
        algo, n_s, r_s, p_s, salt_hex, digest_hex = encoded.split("$", 5)
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def hash_code(code: str) -> str:
    """One-way hash for email verification codes (never store plaintext)."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_numeric_code(digits: int = 6) -> str:
    """Cryptographically strong zero-padded numeric code."""
    upper = 10**digits
    return f"{secrets.randbelow(upper):0{digits}d}"


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
