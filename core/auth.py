"""
core.auth
---------
User accounts and session tokens.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib hashlib) — no extra deps.
For higher-security deployments, swap to argon2-cffi.

Session tokens are random URL-safe strings stored server-side in the
`auth_tokens` table; the client receives the token via an HttpOnly cookie.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from core.config import get_settings
from core.db import cursor, insert_returning_id, now_sql, q
from core.logging_setup import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class User:
    id: int
    username: str


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_HASH_ITER = 200_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return `pbkdf2$<iter>$<salt_hex>$<hash_hex>`."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ITER)
    return f"pbkdf2${_HASH_ITER}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iters, salt_hex, digest_hex = encoded.split("$")
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Base class. Subclasses map to specific HTTP responses."""


class UserAlreadyExists(AuthError): ...
class InvalidCredentials(AuthError): ...
class InvalidToken(AuthError): ...


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def register_user(username: str, password: str) -> User:
    username = username.strip()
    if not username or not password:
        raise AuthError("Username and password required")
    if len(password) < 4:
        raise AuthError("Password must be at least 4 characters")

    pwd_hash = hash_password(password)
    try:
        with cursor() as cur:
            user_id = insert_returning_id(
                cur,
                "INSERT INTO users(username, password_hash) VALUES(?, ?)",
                (username, pwd_hash),
            )
    except Exception as e:
        msg = str(e).upper()
        # SQLite says "UNIQUE constraint failed", Postgres says "duplicate key".
        if "UNIQUE" in msg or "DUPLICATE" in msg:
            raise UserAlreadyExists(f"Username '{username}' already taken") from e
        raise
    log.info("User registered id=%s username=%s", user_id, username)
    return User(id=int(user_id), username=username)


def authenticate(username: str, password: str) -> User:
    with cursor() as cur:
        cur.execute(
            q("SELECT id, username, password_hash FROM users WHERE username=?"),
            (username.strip(),),
        )
        row = cur.fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise InvalidCredentials("Invalid username or password")
    return User(id=row["id"], username=row["username"])


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def create_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(seconds=get_settings().auth.session_ttl_seconds)
    with cursor() as cur:
        cur.execute(
            q("INSERT INTO auth_tokens(token, user_id, expires_at) VALUES(?, ?, ?)"),
            (token, user_id, expires),
        )
    return token


def lookup_token(token: str) -> Optional[User]:
    if not token:
        return None
    with cursor() as cur:
        cur.execute(
            q(
                """
                SELECT u.id, u.username, t.expires_at
                FROM auth_tokens t JOIN users u ON u.id = t.user_id
                WHERE t.token = ?
                """
            ),
            (token,),
        )
        row = cur.fetchone()
    if not row:
        return None
    expires = row["expires_at"]
    # Normalize to UTC-naive for portable comparison.
    # SQLite stores TEXT (naive); Postgres returns timezone-aware datetime.
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires.tzinfo is not None:
        # Convert aware datetime to naive UTC.
        expires = expires.replace(tzinfo=None) if expires.utcoffset() is None \
                 else (expires - expires.utcoffset()).replace(tzinfo=None)
    if expires < datetime.utcnow():
        revoke_token(token)
        return None
    return User(id=row["id"], username=row["username"])


def revoke_token(token: str) -> None:
    if not token:
        return
    with cursor() as cur:
        cur.execute(q("DELETE FROM auth_tokens WHERE token=?"), (token,))


def cleanup_expired_tokens() -> int:
    """Best-effort housekeeping. Call from a periodic task."""
    with cursor() as cur:
        cur.execute(f"DELETE FROM auth_tokens WHERE expires_at < {now_sql()}")
        return cur.rowcount or 0
