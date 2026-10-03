"""Password hashing and JWT helpers.

Uses PBKDF2-HMAC-SHA256 for passwords and a self-contained JWT implementation
so the project has no extra auth dependency.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from server.core.config import settings

PBKDF2_ROUNDS = 260_000


# --------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    """Return `pbkdf2_sha256$iterations$salt$hash` (all base64url encoded)."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return "$".join(
        [
            "pbkdf2_sha256",
            str(PBKDF2_ROUNDS),
            _b64(salt),
            _b64(dk),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
    return hmac.compare_digest(dk, expected)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


# ---------------------------------------------------------------------------- JWT
def _sign(msg: bytes) -> bytes:
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).digest()


def create_access_token(
    subject: str, role: str, expires_minutes: int | None = None
) -> str:
    """Build a signed JWT (HS256) carrying the user id and role."""
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    header = {"alg": settings.ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + minutes * 60,
    }
    seg = (
        _b64(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64(json.dumps(payload, separators=(",", ":")).encode())
    )
    signature = _b64(_sign(seg.encode()))
    return f"{seg}.{signature}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return the payload when the token is valid and unexpired, else None."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError:
        return None
    expected = _b64(_sign(f"{header_b64}.{payload_b64}".encode()))
    if not hmac.compare_digest(expected, signature_b64):
        return None
    try:
        payload = json.loads(_unb64(payload_b64))
    except (ValueError, TypeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
