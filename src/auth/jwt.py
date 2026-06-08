"""JWT authentication utilities.

Handles password hashing/verification via bcrypt and JWT token
creation/decoding using python-jose.  Configuration is pulled from
environment variables so secrets stay out of source control.

Refresh-token rotation
~~~~~~~~~~~~~~~~~~~~~~
* A random opaque string is issued alongside each access JWT.
* Only a SHA-256 hash of the refresh token is stored in the DB.
* On each ``/api/auth/refresh`` call the old token is revoked and a new
  pair (access + refresh) is returned — this is **token rotation**.
* If a revoked token is reused the entire family is invalidated
  (replay-detection).
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-to-a-strong-random-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* suitable for database storage.

    Args:
        plain: The clear-text password to hash.

    Returns:
        UTF-8 encoded bcrypt hash string.
    """
    if not plain:
        raise ValueError("Password must not be empty")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check *plain* against a bcrypt *hashed* value.

    Args:
        plain: The clear-text password to verify.
        hashed: The bcrypt hash to compare against.

    Returns:
        ``True`` if the password matches, ``False`` otherwise.
    """
    if not plain or not hashed:
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT containing *data* as claims.

    Args:
        data: Payload dictionary (typically ``sub``, ``email``, ``role``).
        expires_delta: Optional custom lifetime; defaults to
            ``ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        Encoded JWT string.
    """
    if not data:
        raise ValueError("Token payload must not be empty")
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT.

    Args:
        token: The raw JWT string.

    Returns:
        The decoded payload dictionary.

    Raises:
        jose.JWTError: If the token is invalid, expired, or tampered with.
    """
    if not token:
        raise JWTError("Token must not be empty")
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── Refresh-token helpers ─────────────────────────────────────────────────

def _hash_token(raw_token: str) -> str:
    """Return the hex SHA-256 digest of *raw_token*."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Create a new opaque refresh token.

    Returns:
        A 3-tuple of ``(raw_token, token_hash, expires_at)``.
        The raw token is sent to the client; only the hash is persisted.
    """
    raw = secrets.token_urlsafe(48)
    return raw, _hash_token(raw), datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def new_family_id() -> uuid.UUID:
    """Return a fresh UUID4 to start a new refresh-token family."""
    return uuid.uuid4()


def hash_refresh_token(raw_token: str) -> str:
    """Public wrapper so callers can hash a client-supplied token for lookup."""
    return _hash_token(raw_token)
