import logging

# from .schema import ModelConfigRequest
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status

from src.services.admin_dashboard.service import admin_dashboard
from src.admin.dependencies import get_current_admin
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
    active_model,
    admin_check,
    delete_user,
    get_extraction_config,
    get_user,
    get_user_by_id,
    is_within_extraction_window,
    list_email_accounts,
    # list_mail,
    list_user,
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

@router.get("/admin_dashboard")
def get_admin_dashboard(_admin=Depends(get_current_admin)):
    """Fetch the profile of the currently authenticated admin."""
    try:
        admin_id = _admin.admin_id
        return admin_dashboard(admin_id)
    except ValueError as e:
        logger.warning("[get_profile] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )