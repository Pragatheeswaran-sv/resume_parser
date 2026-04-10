import logging

# from .schema import ModelConfigRequest
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin
from src.admin.schema import (
    AdminCreate,
    AdminLoginRequest,
    AdminUpdate,
    AuthorizedUserCreate,
    AuthorizedUserUpdate,
    BlockToggleRequest,
    ExtractionConfigUpdate,
    ExtractionToggleRequest,
    SSOLoginRequest,
)
from src.services.admin.service import (
    admin_check,
    delete_auth_mail,
    get_extraction_config,
    is_within_extraction_window,
    list_email_accounts,
    list_mail,
    new_admin,
    new_auth,
    pause_extraction,
    profile,
    resume_extraction,
    sso_user_login,
    toggle_block,
    toggle_extraction,
    trigger_extraction,
    update_admin_profile,
    update_auth_mail,
    update_extraction_config,
    list_model,
    model_version, 
    new_model_version,
    model_config, 
    get_model,
    create_model
)
from typing import List, Dict, Any
# from src.services.admin.service import (
#     admin_check, create_model,
#     delete_auth_mail, new_admin,
#     list_mail, new_auth,
#     update_auth_mail, list_model,
#     model_version, new_model_version,
#     model_config, get_model
# )
from src.utils.response import serialize_response

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
def create_admin(payload: AdminCreate):
    """Register a new administrator account.

    Accepts a validated ``AdminCreate`` body with email, password, and
    optional name.  Returns the newly created admin's ID.
    """
    try:
        return new_admin(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.get("/admin_profile")
def get_profile(admin_id):
    """Fetch the profile of the currently authenticated admin."""
    try:
        return profile(admin_id)
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
        return admin_check(body.email, body.password)
    except ValueError as e:
        logger.warning("[admin_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )

@router.patch("/admin_update")
def update_admin(admin_id: str, payload: AdminUpdate):
    """Update an existing admin's profile."""
    try:
        return update_admin_profile(admin_id, payload.model_dump())
    except ValueError as e:
        logger.warning("[update_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.post("/auth/sso/login")
def sso_login(body: SSOLoginRequest):
    """Accept an SSO-verified email and return a JWT for the user.

    The frontend should verify the SSO token with the identity provider
    (Google, Zoho, or Microsoft) first, then call this endpoint with the
    verified email and optional provider name.
    """
    try:
        return sso_user_login(body.email, provider=body.provider)
    except ValueError as e:
        logger.warning("[sso_login] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": str(e)},
        )


# ── Legacy auth-mail CRUD (kept for backward-compat) ────────────────────

@router.get("/list_auth_mail")
def get_auth_mails():
    """List all active authorized email accounts."""
    try:
        return list_mail()
    except ValueError as e:
        logger.warning("[list_auth_mail] Error: %s", str(e), exc_info=True)
        logger.warning("[list_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/create_auth_mail")
def new_auth_mail(payload: AuthorizedUserCreate):
    """Register a new authorized email account for IMAP extraction.

    Accepts a validated ``AuthorizedUserCreate`` body with email,
    optional IMAP password, and connection metadata.
    """
    try:
        return new_auth(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_auth_mail] Error: %s", str(e), exc_info=True)
        logger.warning("[create_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/delete_auth_mail/")
def delete_auth(auth_mail_id: str):
    """Soft-delete an authorized email account by marking it inactive.

    Args:
        auth_mail_id: UUID of the auth mail record to deactivate.
    """
    if not auth_mail_id or not auth_mail_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "auth_mail_id is required"},
        )
    try:
        return delete_auth_mail(auth_mail_id)
    except ValueError as e:
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/update_auth_mail/")
def update_auth(auth_mail_id: str, payload: AuthorizedUserUpdate):
    """Update fields on an existing authorized email account.

    Args:
        auth_mail_id: UUID of the auth mail record to update.
        payload: Validated partial update body.
    """
    if not auth_mail_id or not auth_mail_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "auth_mail_id is required"},
        )
    try:
        return update_auth_mail(auth_mail_id, payload.model_dump(exclude_unset=True))
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
    """Update extraction schedule (interval, pause flag, time window)."""
    try:
        return update_extraction_config(
            interval_minutes=body.interval_minutes,
            is_paused=body.is_paused,
            window_enabled=body.window_enabled,
            window_start_time=body.window_start_time,
            window_end_time=body.window_end_time,
            window_timezone=body.window_timezone,
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
    force: bool = False,
    _admin=Depends(get_current_admin),
):
    """Manually trigger extraction for all accounts.

    Args:
        force: If True, bypass time-window restriction.
    """
    try:
        if not force and not is_within_extraction_window():
            logger.info(
                "Manual trigger blocked: outside configured time window (force=%s)",
                force,
            )
            return {
                "status": status.HTTP_200_OK,
                "message": "Skipping extraction: outside configured time window",
            }
        if force:
            logger.info("Manual trigger: force=true — bypassing time window check")
        return trigger_extraction()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/admin/extraction/trigger/{auth_mail_id}")
def trigger_single(
    auth_mail_id: str,
    force: bool = False,
    _admin=Depends(get_current_admin),
):
    """Manually trigger extraction for a specific email account.

    Args:
        auth_mail_id: UUID of the email account to extract.
        force: If True, bypass time-window restriction.
    """
    try:
        if not force and not is_within_extraction_window():
            logger.info(
                "Manual trigger for %s blocked: outside configured time window (force=%s)",
                auth_mail_id,
                force,
            )
            return {
                "status": status.HTTP_200_OK,
                "message": "Skipping extraction: outside configured time window",
            }
        if force:
            logger.info(
                "Manual trigger for %s: force=true — bypassing time window check",
                auth_mail_id,
            )
        return trigger_extraction(auth_mail_id=auth_mail_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

            # detail={
            #     "status": "error",
            #     "message": str(e),
            # })
    
@router.get(
    "/list_model/",
    # summary="List active AI models",
    # description=(
    #     "Fetch all active AI models configured for admin workflows and "
    #     "resume processing."
    # ),
    # response_description="A list of active AI model entries.",
)
def list_models() :
    """Return all active models available in the system."""
    try:
        return list_model()
    except ValueError as e:
        logger.warning("[list_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })


@router.post(
    "/create_model/",
    summary="Create a new AI model",
    description="Create and store a new active AI model by model name.",
    response_description="Created AI model details.",
)
def add_model(payload: Dict[str, Any]):
    """Create a new model with the provided ``model_name``."""
    try:
        return create_model(payload)
    except ValueError as e:
        logger.warning("[create_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.get("/list_model_versions/")
def list_model_versions(model_id):
    """
    List Model Versions

    Retrieves all active versions for a given AI model using the provided model ID.

    This endpoint first checks whether the AI model exists and is active.
    If the model is found, it returns all active versions associated with that model.

    Args:
        model_id (str): The unique identifier of the AI model.

    Returns:
        dict: A response object containing:
            - status (int): HTTP status code
            - message (str): Success message
            - data (list): List of active model versions

    Response Includes:
        - model_version_id
        - version_name

    Raises:
        HTTPException:
            - 400 Bad Request: If the model is not found or no versions exist.
    """
    
    try:
       return model_version(model_id)
    except ValueError as e:
        logger.warning("[list_model_versions] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    

@router.post("/new_model_version/")
def create_model_version(model_id, payload: Dict[str, Any]):
    """
        Create Model Version

        Creates a new version entry for a given AI model using the provided model ID
        and request payload.

        This endpoint first validates whether the AI model exists and is active.
        If the model is valid, it creates a new active version associated with that model.

        Args:
            model_id (str): The unique identifier of the AI model.
            payload (Dict[str, Any]): Request body containing model version details.

        Request Body:
            - version_name (str): Name of the new model version

        Returns:
            dict: A response object containing:
                - status (int): HTTP status code
                - message (str): Success message
                - data (dict): Newly created model version details

        Response Includes:
            - model_version_id
            - version_name

        Raises:
            HTTPException:
                - 400 Bad Request: If the model does not exist or version name is invalid.
    """
    try:
        return new_model_version(model_id, payload)
    except ValueError as e:
        logger.warning("[new_model_version] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.post("/model_config/")
def get_model_config(payload: Dict[str, Any], admin_id):
    """
        Create Model Configuration

        Creates a new AI model configuration for a given admin using the provided
        model ID, model version ID, and configuration details.

        This endpoint validates whether:
        - the admin ID is provided
        - the AI model exists and is active
        - the AI model version exists and is active

        If validation succeeds, a new model configuration is created and stored.

        Args:
            payload (Dict[str, Any]): Request body containing model configuration details.
            admin_id (str): The unique identifier of the admin creating the configuration.

        Request Body:
            - model_id (str): Unique AI model ID
            - model_version_id (str): Unique AI model version ID
            - apikey (str, optional): API key for the selected model
            - version (str, optional): External provider version name
            - max_tokens (int, optional): Maximum token limit
            - temperature (float, optional): Model temperature value

        Returns:
            dict: A response object containing:
                - status (int): HTTP status code
                - message (str): Success message
                - data (dict): Created model configuration details

        Response Includes:
            - model_config_id
            - model_id
            - model_name
            - model_version_id
            - model_version_name
            - admin_id
            - apikey
            - max_tokens

        Raises:
            HTTPException:
                - 400 Bad Request: If admin ID, model, or model version is invalid.
    """
    try:
        return model_config(payload, admin_id)
    except ValueError as e:
        logger.warning("[get_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.get("/get_model_config/")
def fetch_model_config(admin_id):
    """
        Fetch Model Configuration

        Retrieves the active AI model configuration associated with the given admin ID.

        This endpoint fetches the configured AI model, model version, API key,
        token settings, and other related configuration details for the specified admin.

        Args:
            admin_id (str): The unique identifier of the admin.

        Returns:
            dict: A response object containing:
                - status (int): HTTP status code
                - message (str): Success message
                - data (dict): Active model configuration details

        Response Includes:
            - model_config_id
            - model_id
            - model_name
            - model_version_id
            - model_version_name
            - admin_id
            - apikey
            - max_tokens
            - temperature

        Raises:
            HTTPException:
                - 400 Bad Request: If admin ID is missing or no active configuration is found.
    """
    try:
        return get_model(admin_id)
    except ValueError as e:
        logger.warning("[fetch_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })