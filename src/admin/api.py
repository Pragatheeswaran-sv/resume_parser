import logging

# from .schema import ModelConfigRequest
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin, get_current_user
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
    SSOLoginRequest,
    Validate_new_job,
)
# from src.services.resume_filter.service import export
from src.services.admin.service import (
    admin_check,
    delete_user,
    get_extraction_config,
    get_user,
    get_user_by_id,
    is_within_extraction_window,
    list_email_accounts,
    list_mail,
    new_admin,
    new_auth,
    new_job,
    pause_extraction,
    profile,
    resume_extraction,
    sso_user_login,
    toggle_block,
    toggle_extraction,
    toggle_model,
    trigger_extraction,
    update_admin_profile,
    update_user,
    update_extraction_config,
    list_model,
    model_version, 
    # new_model_version,
    model_config, 
    get_model,
    create_model
)
from typing import List, Dict, Any
# from src.services.admin.service import (
#     admin_check, create_model,
#     delete_user, new_admin,
#     list_mail, new_auth,
#     update_user, list_model,
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
def get_profile(_admin=Depends(get_current_admin)):
    """Fetch the profile of the currently authenticated admin."""
    try:
        admin_id = _admin.admin_id
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

@router.patch("/update_admin")
def update_admin(payload: AdminUpdate, _admin=Depends(get_current_admin)):
    """Update an existing admin's profile."""
    try:
        admin_id = _admin.admin_id
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

@router.get("/list_users")
def get_users(page, page_size, sort_by = None, sort_order = None, filter_column = None, filter_value = None, _admin = Depends(get_current_admin)):
    """List all active authorized email accounts."""
    try:
        admin = _admin.admin_id
        if not admin:
            raise ValueError("Admin authentication required")
        return list_mail(page, page_size, sort_by, sort_order, filter_column, filter_value)
    except ValueError as e:
        logger.warning("[list_users] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.post("/create_user")
def new_user(payload: AuthorizedUserCreate, _admin=Depends(get_current_admin)):
    """Register a new authorized email account for IMAP extraction.

    Accepts a validated ``AuthorizedUserCreate`` body with email,
    optional IMAP password, and connection metadata.
    """
    try:
        admin_id = _admin.admin_id
        return new_auth(payload.model_dump(), admin_id)
    except ValueError as e:
        logger.warning("[create_user] Error: %s", str(e), exc_info=True)
        logger.warning("[create_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.get('/user_profile')
def get_user_profile(_user = Depends(get_current_user)):
    try:
        user_id = _user.user_id
        return get_user(user_id)
    except ValueError as e:
        logger.warning("[particular_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.get('/particular_user')
def get_particular_user(user_id, _admin=Depends(get_current_admin)):
    try:
        admin_id = _admin.admin_id
        return get_user_by_id(user_id, admin_id)
    except ValueError as e:
        logger.warning("[particular_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.patch("/delete_user/")
def delete_auth(user_id, _admin=Depends(get_current_admin)):
# def delete_auth():
    """Soft-delete an authorized email account by marking it inactive.

    Args:
        user_id: UUID of the auth mail record to deactivate.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "user_id is required"},
        )
    try:
        admin_id = _admin.admin_id
        return delete_user(user_id, admin_id)
    except ValueError as e:
        logger.warning("[delete_user] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.patch("/update_user/")
# def update_auth(user_id: str, payload: AuthorizedUserUpdate):
def update_auth(payload: AuthorizedUserUpdate, user_id, _admin=Depends(get_current_admin)):
    """Update fields on an existing authorized email account.

    Args:
        user_id: UUID of the auth mail record to update.
        payload: Validated partial update body.
    """
    # if not user_id or not user_id.strip():
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail={"status": "error", "message": "user_id is required"},
    #     )
    try:
        # return update_user(user_id, payload.model_dump(exclude_unset=True))
        admin_id = _admin.admin_id
        return update_user(payload.model_dump(exclude_unset=True), user_id, admin_id)
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
        return list_email_accounts()
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
        return toggle_extraction(user_id, body.extraction_enabled)
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
        return toggle_block(user_id, body.is_blocked)
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


@router.put("/admin/extraction/update_config")
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
            schedule_type = body.schedule_type,
            weekday = body.weekday
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

@router.post("/admin/extraction/create_schedule")
def add_job(payload : Validate_new_job, _admin=Depends(get_current_admin)):
    try:
        admin_id = _admin.admin_id
        return new_job(payload, admin_id)
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
    """Manually trigger extraction for a specific email account.

    Args:
        user_id: UUID of the email account to extract.
        force: If True, bypass time-window restriction.
    """
    try:
        if not force and not is_within_extraction_window():
            logger.info(
                "Manual trigger for %s blocked: outside configured time window (force=%s)",
                user_id,
                force,
            )
            return {
                "status": status.HTTP_200_OK,
                "message": "Skipping extraction: outside configured time window",
            }
        if force:
            logger.info(
                "Manual trigger for %s: force=true — bypassing time window check",
                user_id,
            )
        return trigger_extraction(user_id=user_id)
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
def add_model(payload: CreateModelValidate):
    """Create a new model with the provided ``model_name``."""
    try:
        return create_model(payload.model_dump())
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
    

# @router.post("/new_model_version/")
# def create_model_version(model_id, payload: Dict[str, Any]):
#     """
#         Create Model Version

#         Creates a new version entry for a given AI model using the provided model ID
#         and request payload.

#         This endpoint first validates whether the AI model exists and is active.
#         If the model is valid, it creates a new active version associated with that model.

#         Args:
#             model_id (str): The unique identifier of the AI model.
#             payload (Dict[str, Any]): Request body containing model version details.

#         Request Body:
#             - version_name (str): Name of the new model version

#         Returns:
#             dict: A response object containing:
#                 - status (int): HTTP status code
#                 - message (str): Success message
#                 - data (dict): Newly created model version details

#         Response Includes:
#             - model_version_id
#             - version_name

#         Raises:
#             HTTPException:
#                 - 400 Bad Request: If the model does not exist or version name is invalid.
#     """
#     try:
#         return new_model_version(model_id, payload)
#     except ValueError as e:
#         logger.warning("[new_model_version] Error: %s", str(e), exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail={
#                 "status": "error",
#                 "message": str(e),
#             })

@router.post("/model_config/")
# def get_model_config(payload: Dict[str, Any], admin_id):
def get_model_config(payload: Dict[str, Any], _admin=Depends(get_current_admin)):
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
        admin_id = _admin.admin_id
        return model_config(payload, admin_id)
        # return model_config(payload)
    except ValueError as e:
        logger.warning("[get_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.get("/get_model_config/")
# def fetch_model_config(admin_id):
def fetch_model_config(page, page_size, sort_by = None, sort_order = None, filter_column = None, filter_value = None, _admin=Depends(get_current_admin)):
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
        admin_id = _admin.admin_id
        return get_model(page, page_size, sort_by, sort_order, filter_column, filter_value, admin_id)
    except ValueError as e:
        logger.warning("[fetch_model_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.patch('/enable_ai_model')
def enable_model(model_config_id, _admin=Depends(get_current_admin)):
    """
        Enable AI Model Configuration

        Activates a specific AI model configuration for the authenticated admin.
        When a model configuration is enabled, all other configurations associated
        with the same admin will be automatically disabled to ensure that only
        one model remains active at a time.

        This endpoint is useful for switching between different AI models or
        model versions configured by the admin.

        Endpoint:
            PATCH /enable_ai_model

        Args:
            model_config_id (str):
                The unique identifier of the model configuration to be enabled.

            _admin (Admin):
                The currently authenticated admin user (injected via dependency).

        Returns:
            dict: A response object containing:
                - status (str): "success" or "error"
                - message (str): Description of the operation result
                - data (dict, optional): Details of the updated model configuration

        Behavior:
            - Sets `is_active = True` for the given model_config_id
            - Sets `is_active = False` for all other configurations of the same admin

        Raises:
            HTTPException:
                - 400 Bad Request:
                    - If model_config_id is invalid
                    - If the model configuration does not belong to the admin
                    - If update operation fails
    """
    try:
        admin_id = _admin.admin_id
        return toggle_model(model_config_id, admin_id)
    except ValueError as e:
        logger.warning("[enable_model] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })