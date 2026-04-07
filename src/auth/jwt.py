"""JWT authentication utilities.

Handles password hashing/verification via bcrypt and JWT token
creation/decoding using python-jose.  Configuration is pulled from
environment variables so secrets stay out of source control.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-to-a-strong-random-secret-key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


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
