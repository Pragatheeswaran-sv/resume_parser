import logging
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin
from src.admin.schema import (
    AdminLoginRequest,
    BlockToggleRequest,
    ExtractionConfigUpdate,
    ExtractionToggleRequest,
    SSOLoginRequest,
)
from src.services.admin.service import (
    admin_check,
    delete_auth_mail,
    get_extraction_config,
    list_email_accounts,
    list_mail,
    new_admin,
    new_auth,
    pause_extraction,
    resume_extraction,
    sso_user_login,
    toggle_block,
    toggle_extraction,
    trigger_extraction,
    update_auth_mail,
    update_extraction_config,
)

load_dotenv()
logger = logging.getLogger(__name__)


# ── Public routes (no auth guard) ─────────────────────────────────────────

router = APIRouter(
    prefix="/api",
    tags=["Admin"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/create_admin")
def create_admin(payload: Dict[str, Any]):
    try:
        return new_admin(payload)
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/login")
def admin_login(body: AdminLoginRequest):
    """Authenticate admin with email + password and return a JWT."""
    try:
        return admin_check(body.email, body.password)
    except ValueError as e:
        logger.warning("[admin_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/auth/sso/login")
def sso_login(body: SSOLoginRequest):
    """Accept an SSO-verified email and return a JWT for the user.

    The frontend should verify the SSO token with the identity provider
    first, then call this endpoint with the verified email.
    """
    try:
        return sso_user_login(body.email)
    except ValueError as e:
        logger.warning("[sso_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )


# ── Legacy auth-mail CRUD (kept for backward-compat) ────────────────────

@router.get("/list_auth_mail")
def get_auth_mails():
    try:
        return list_mail()
    except ValueError as e:
        logger.warning("[list_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/create_auth_mail")
def new_auth_mail(payload: Dict[str, Any]):
    try:
        return new_auth(payload)
    except ValueError as e:
        logger.warning("[create_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/delete_auth_mail/")
def delete_auth(auth_mail_id: str):
    try:
        return delete_auth_mail(auth_mail_id)
    except ValueError as e:
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/update_auth_mail/")
def update_auth(auth_mail_id: str, payload: Dict[str, Any]):
    try:
        return update_auth_mail(auth_mail_id, payload)
    except ValueError as e:
        logger.warning("[update_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Admin-protected endpoints  (require valid admin JWT)
# ═══════════════════════════════════════════════════════════════════════════

# ── 1. Connected email accounts overview ─────────────────────────────────

@router.get("/admin/email-accounts")
def email_accounts_overview(_admin=Depends(get_current_admin)):
    """List all connected email accounts with extraction status."""
    try:
        return list_email_accounts()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ── 2 & 3. Per-account extraction / block toggles ───────────────────────

@router.patch("/admin/email-accounts/{auth_mail_id}/extraction")
def set_extraction(
    auth_mail_id: str,
    body: ExtractionToggleRequest,
    _admin=Depends(get_current_admin),
):
    """Enable or disable extraction for a specific email account."""
    try:
        return toggle_extraction(auth_mail_id, body.extraction_enabled)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/admin/email-accounts/{auth_mail_id}/block")
def set_block(
    auth_mail_id: str,
    body: BlockToggleRequest,
    _admin=Depends(get_current_admin),
):
    """Block or unblock a specific email account."""
    try:
        return toggle_block(auth_mail_id, body.is_blocked)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ── 4. Extraction control panel ─────────────────────────────────────────

@router.get("/admin/extraction/config")
def get_config(_admin=Depends(get_current_admin)):
    """Retrieve global extraction schedule configuration."""
    try:
        return get_extraction_config()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.put("/admin/extraction/config")
def update_config(
    body: ExtractionConfigUpdate,
    _admin=Depends(get_current_admin),
):
    """Update extraction schedule (interval, pause flag)."""
    try:
        return update_extraction_config(
            interval_minutes=body.interval_minutes,
            is_paused=body.is_paused,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/pause")
def pause(_admin=Depends(get_current_admin)):
    """Globally pause all extraction jobs."""
    try:
        return pause_extraction()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/resume")
def resume(_admin=Depends(get_current_admin)):
    """Globally resume extraction jobs."""
    try:
        return resume_extraction()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/trigger")
def trigger_all(
    _admin=Depends(get_current_admin),
):
    """Manually trigger extraction for all accounts."""
    try:
        return trigger_extraction()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/trigger/{auth_mail_id}")
def trigger_single(
    auth_mail_id: str,
    _admin=Depends(get_current_admin),
):
    """Manually trigger extraction for a specific email account."""
    try:
        return trigger_extraction(auth_mail_id=auth_mail_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
