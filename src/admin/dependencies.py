import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from db.connection import SessionLocal
from src.admin.models import Admin, AuthMail
from src.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

OPEN_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/create_admin",
    "/api/admin/login",
    "/api/auth/sso/login",
}

ADMIN_PREFIX = "/api/admin"


def _extract_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> dict:
    """Decode the Bearer token and return the JWT payload, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependencies ─────────────────────────────────────────────────

def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    """Verify the caller holds a valid *admin* JWT and return the Admin row."""
    payload = _extract_token_payload(credentials)

    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "message": "Admin access required"},
        )

    db = SessionLocal()
    try:
        admin = (
            db.query(Admin)
            .filter(
                Admin.admin_id == payload["sub"],
                Admin.is_active.is_(True),
            )
            .first()
        )
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Admin account not found or deactivated"},
            )
        return admin
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    """Verify the caller holds a valid *user* JWT and return the AuthMail row."""
    payload = _extract_token_payload(credentials)

    if payload.get("role") != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "message": "User access required"},
        )

    db = SessionLocal()
    try:
        account = (
            db.query(AuthMail)
            .filter(
                AuthMail.auth_mail_id == payload["sub"],
                AuthMail.is_active.is_(True),
                AuthMail.is_blocked.is_(False),
            )
            .first()
        )
        if not account:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "User account not found, blocked, or deactivated"},
            )
        return account
    finally:
        db.close()


def get_current_admin_or_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    """Accept either an admin or a user JWT. Returns (role, db_object)."""
    payload = _extract_token_payload(credentials)
    role = payload.get("role")

    db = SessionLocal()
    try:
        if role == "admin":
            obj = (
                db.query(Admin)
                .filter(Admin.admin_id == payload["sub"], Admin.is_active.is_(True))
                .first()
            )
        elif role == "user":
            obj = (
                db.query(AuthMail)
                .filter(
                    AuthMail.auth_mail_id == payload["sub"],
                    AuthMail.is_active.is_(True),
                    AuthMail.is_blocked.is_(False),
                )
                .first()
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Invalid token role"},
            )

        if not obj:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Account not found or deactivated"},
            )
        return role, obj
    finally:
        db.close()


# ── Access-restriction middleware (JWT-aware) ────────────────────────────

class AllowedEmailMiddleware(BaseHTTPMiddleware):
    """Reject non-open, non-admin requests that lack a valid JWT.

    Open paths and ``/api/admin/*`` are exempt — admin endpoints carry
    their own guard via ``get_current_admin``.  For everything else the
    middleware validates the Bearer token and checks that the user's
    email exists in ``auth_mail``.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in OPEN_PATHS or path.startswith(ADMIN_PREFIX):
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"status": "error", "message": "Authorization header required"},
            )

        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_access_token(token)
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"status": "error", "message": "Invalid or expired token"},
            )

        user_email = payload.get("email")
        if not user_email:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"status": "error", "message": "Token missing email claim"},
            )

        db = SessionLocal()
        try:
            account = (
                db.query(AuthMail)
                .filter(
                    AuthMail.email_address == user_email,
                    AuthMail.is_active.is_(True),
                    AuthMail.is_blocked.is_(False),
                )
                .first()
            )
        finally:
            db.close()

        if not account and payload.get("role") != "admin":
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"status": "error", "message": "Access denied: email not approved"},
            )

        return await call_next(request)
