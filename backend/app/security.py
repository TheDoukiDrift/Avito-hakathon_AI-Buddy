"""Password hashing and hand-rolled HMAC bearer tokens.

Deliberately dependency-free: the scaffold does not need JWT libraries, and the
token format stays readable in a debugger (`payload.signature`, both base64url).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.config import get_settings

_PBKDF2_ITERATIONS = 120_000
_SALT_BYTES = 16


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt_hex = salt or secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS
    )
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt_hex}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, expected = stored.split("$", 3)
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def create_token(user_id: int, *, ttl_seconds: int | None = None) -> str:
    settings = get_settings()
    ttl = settings.token_ttl_seconds if ttl_seconds is None else ttl_seconds
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + ttl}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.secret_key.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{encoded}.{_b64encode(signature)}"


def decode_token(token: str) -> int | None:
    """Return the user id, or None when the token is malformed, forged or expired."""
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(
            get_settings().secret_key.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_b64decode(signature), expected):
            return None
        payload = json.loads(_b64decode(encoded))
        if int(payload["exp"]) < int(time.time()):
            return None
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
