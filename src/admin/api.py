"""API route endpoints for administration and configuration.

All routes delegate cleanly to admin_service class methods,
maintaining complete separation between routing and business logic.
"""

import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin, get_current_admin_or_user, get_current_user
from src.admin.schema import (
    AdminCreate,
    AdminLoginRequest,
    AdminUpdate,
    AuthorizedUserCreate,
    AuthorizedUserUpdate,
    BlockToggleRequest,
    CreateModelValidate,
    ExtractionConfigUpdate,
    ExtractionToggleRequest,
    RefreshTokenRequest,
    SSOLoginRequest,
    Validate_new_job,
)
from src.admin.service import admin_service

load_dotenv()
logger = logging.getLogger(__name__)

# Module-level aliases to preserve unittest mock patch targets (e.g. patch("src.admin.api.new_auth"))
new_auth = admin_service.new_auth
get_user = admin_service.get_user
get_user_by_id = admin_service.get_user_by_id
delete_user = admin_service.delete_user
update_user = admin_service.update_user
list_user = admin_service.list_user


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
def create_admin(payload: AdminCreate):
    """Register a new administrator account."""
    try:
        return admin_service.new_admin(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin_profile")
def get_profile(_admin=Depends(get_current_admin)):
    """Fetch the profile of the currently authenticated admin."""
    try:
        return admin_service.profile(_admin.admin_id)
    except ValueError as e:
        logger.warning("[get_profile] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/login")
def admin_login(body: AdminLoginRequest):
    """Authenticate admin with email + password and return a JWT."""
    try:
        return admin_service.admin_check(body.email, body.password)
    except ValueError as e:
        logger.warning("[admin_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/update_admin")
def update_admin(payload: AdminUpdate, _admin=Depends(get_current_admin)):
    """Update an existing admin's profile."""
    try:
        return admin_service.update_admin_profile(_admin.admin_id, payload.model_dump())
    except ValueError as e:
        logger.warning("[update_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/auth/sso/login")
def sso_login(body: SSOLoginRequest):
    """Accept an SSO-verified email and return a JWT for the user."""
    try:
        return admin_service.sso_user_login(body.email, provider=body.provider)
    except ValueError as e:
        logger.warning("[sso_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/auth/refresh")
def refresh_token(body: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        return admin_service.rotate_refresh_token(body.refresh_token)
    except ValueError as e:
        logger.warning("[refresh_token] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/auth/logout")
def logout(body: RefreshTokenRequest):
    """Revoke all refresh tokens in the same family (log out)."""
    try:
        return admin_service.revoke_refresh_tokens(body.refresh_token)
    except ValueError as e:
        logger.warning("[logout] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ── Legacy auth-mail CRUD (kept for backward-compat) ────────────────────

@router.get("/list_users")
def get_users(page, page_size, sort_by=None, sort_order=None, filter_column=None, filter_value=None, _admin=Depends(get_current_admin)):
    """List all active authorized email accounts."""
    try:
        if not _admin or not _admin.admin_id:
            raise ValueError("Admin authentication required")
        return admin_service.list_user(page, page_size, sort_by, sort_order, filter_column, filter_value)
    except ValueError as e:
        logger.warning("[list_users] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/create_user")
def new_user(payload: AuthorizedUserCreate, _admin=Depends(get_current_admin)):
    """Register a new authorized email account for IMAP extraction."""
    try:
        return admin_service.new_auth(payload.model_dump(), _admin.admin_id)
    except ValueError as e:
        logger.warning("[create_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/user_profile")
def get_user_profile(_user=Depends(get_current_user)):
    """Retrieve profile for the currently authenticated user."""
    try:
        return admin_service.get_user(_user.user_id)
    except ValueError as e:
        logger.warning("[particular_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/particular_user")
def get_particular_user(user_id, _admin=Depends(get_current_admin)):
    """Retrieve specific user details by user ID (admin only)."""
    try:
        return admin_service.get_user_by_id(user_id, _admin.admin_id)
    except ValueError as e:
        logger.warning("[particular_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/delete_user/")
def delete_auth(user_id, _admin=Depends(get_current_admin)):
    """Soft-delete an authorized email account by marking it inactive."""
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "user_id is required"},
        )
    try:
        return admin_service.delete_user(user_id, _admin.admin_id)
    except ValueError as e:
        logger.warning("[delete_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/update_user/")
def update_auth(payload: AuthorizedUserUpdate, user_id, _role=Depends(get_current_admin_or_user)):
    """Update fields on an existing authorized email account."""
    try:
        role = _role['role']
        if role == 'admin':
            current_user_id = _role['data'].admin_id
        else:
            current_user_id = _role['data'].user_id
        return admin_service.update_user(payload.model_dump(exclude_unset=True), user_id, current_user_id, role)
    except ValueError as e:
        logger.warning("[update_user] Error: %s", str(e), exc_info=True)
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
        return admin_service.list_email_accounts()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ── 2 & 3. Per-account extraction / block toggles ───────────────────────

@router.patch("/admin/email-accounts/{user_id}/extraction")
def set_extraction(
    user_id: str,
    body: ExtractionToggleRequest,
    _admin=Depends(get_current_admin),
):
    """Enable or disable extraction for a specific email account."""
    try:
        return admin_service.toggle_extraction(user_id, body.extraction_enabled)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/admin/email-accounts/{user_id}/block")
def set_block(
    user_id: str,
    body: BlockToggleRequest,
    _admin=Depends(get_current_admin),
):
    """Block or unblock a specific email account."""
    try:
        return admin_service.toggle_block(user_id, body.is_blocked)
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
        return admin_service.get_extraction_config()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.put("/admin/extraction/update_config")
def update_config(
    body: ExtractionConfigUpdate,
    _admin=Depends(get_current_admin),
):
    """Update extraction schedule (interval, pause flag, time window)."""
    try:
        return admin_service.update_extraction_config(
            interval_minutes=body.interval_minutes,
            is_paused=body.is_paused,
            window_enabled=body.window_enabled,
            window_start_time=body.window_start_time,
            window_end_time=body.window_end_time,
            window_timezone=body.window_timezone,
            schedule_type=body.schedule_type,
            weekday=body.weekday,
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
        return admin_service.pause_extraction()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/resume")
def resume(_admin=Depends(get_current_admin)):
    """Globally resume extraction jobs."""
    try:
        return admin_service.resume_extraction()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/trigger")
def trigger_all(
    force: bool = False,
    _admin=Depends(get_current_admin),
):
    """Manually trigger extraction for all accounts."""
    try:
        return admin_service.trigger_all(force=force)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/create_schedule")
def add_job(payload: Validate_new_job, _admin=Depends(get_current_admin)):
    """Create a new extraction schedule job."""
    try:
        return admin_service.new_job(payload, _admin.admin_id)
    except ValueError as e:
        logger.warning("[create new_job] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error in creating new job", "message": str(e)},
        )


@router.post("/admin/extraction/trigger/{user_id}")
def trigger_single(
    user_id: str,
    force: bool = False,
    _admin=Depends(get_current_admin),
):
    """Manually trigger extraction for a specific email account."""
    try:
        return admin_service.trigger_single(user_id=user_id, force=force)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ── AI Models ─────────────────────────────────────────────────────────────

@router.get("/list_model/")
def list_models():
    """Return all active models available in the system."""
    try:
        return admin_service.list_model()
    except ValueError as e:
        logger.warning("[list_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post(
    "/create_model/",
    summary="Create a new AI model",
    description="Create and store a new active AI model by model name.",
    response_description="Created AI model details.",
)
def add_model(payload: CreateModelValidate):
    """Create a new model with the provided model_name."""
    try:
        return admin_service.create_model(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/list_model_versions/")
def list_model_versions(model_id):
    """Retrieves all active versions for a given AI model using the provided model ID."""
    try:
        return admin_service.model_version(model_id)
    except ValueError as e:
        logger.warning("[list_model_versions] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/model_config/")
def get_model_config(payload: Dict[str, Any], _admin=Depends(get_current_admin)):
    """Creates a new AI model configuration for a given admin."""
    try:
        return admin_service.model_config(payload, _admin.admin_id)
    except ValueError as e:
        logger.warning("[get_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/reorder_model_priority/")
def reorder_priority(model_config_id, new_priority, _admin=Depends(get_current_admin)):
    """Reorders model priority queue position."""
    try:
        return admin_service.reorder_model_priority(model_config_id, int(new_priority), _admin.admin_id)
    except ValueError as e:
        logger.warning("[reorder_priority] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/get_model_config/")
def fetch_model_config(page, page_size, sort_by=None, sort_order=None, filter_column=None, filter_value=None, _admin=Depends(get_current_admin)):
    """Retrieves active AI model configuration associated with the given admin ID."""
    try:
        return admin_service.get_model(page, page_size, sort_by, sort_order, filter_column, filter_value, _admin.admin_id)
    except ValueError as e:
        logger.warning("[fetch_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/enable_ai_model")
def enable_model(model_config_id, _admin=Depends(get_current_admin)):
    """Activates a specific AI model configuration for the authenticated admin."""
    try:
        return admin_service.toggle_model(model_config_id, _admin.admin_id)
    except ValueError as e:
        logger.warning("[enable_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/show_active_model")
def show_active_model(_admin=Depends(get_current_admin)):
    """Retrieves the currently active AI model configuration for the authenticated admin."""
    try:
        return admin_service.active_model(_admin.admin_id)
    except ValueError as e:
        logger.warning("[show_active_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )