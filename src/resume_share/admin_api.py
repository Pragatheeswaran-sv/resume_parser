import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin
from src.resume_share.schemas import (
    EmailProviderConfigCreate,
    EmailProviderConfigUpdate,
    EmailTemplateCreate,
    EmailTemplateUpdate,
)
from src.services.resume_share.email_config_service import (
    create_email_provider_config,
    list_email_provider_configs,
    get_email_provider_config,
    update_email_provider_config,
    delete_email_provider_config,
    create_email_template,
    list_email_templates,
    get_email_template,
    update_email_template,
    delete_email_template,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Email-Config"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


# ═══════════════════════════════════════════════════════════════════════════
#  Email Provider Config CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/admin/email-provider-config")
def create_provider_config(
    payload: EmailProviderConfigCreate,
    _admin=Depends(get_current_admin),
):
    """Create a new email provider configuration (admin only)."""
    try:
        return create_email_provider_config(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-provider-config")
def list_provider_configs(_admin=Depends(get_current_admin)):
    """List all email provider configurations (admin only)."""
    try:
        return list_email_provider_configs()
    except ValueError as e:
        logger.warning("[list_provider_configs] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-provider-config/{config_id}")
def get_provider_config(config_id: str, _admin=Depends(get_current_admin)):
    """Get a specific email provider configuration by ID (admin only)."""
    try:
        return get_email_provider_config(config_id)
    except ValueError as e:
        logger.warning("[get_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.put("/admin/email-provider-config/{config_id}")
def update_provider_config(
    config_id: str,
    payload: EmailProviderConfigUpdate,
    _admin=Depends(get_current_admin),
):
    """Update an email provider configuration (admin only)."""
    try:
        return update_email_provider_config(
            config_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        logger.warning("[update_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.delete("/admin/email-provider-config/{config_id}")
def delete_provider_config(config_id: str, _admin=Depends(get_current_admin)):
    """Delete an email provider configuration (admin only)."""
    try:
        return delete_email_provider_config(config_id)
    except ValueError as e:
        logger.warning("[delete_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Email Template CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/admin/email-templates")
def create_template(
    payload: EmailTemplateCreate,
    _admin=Depends(get_current_admin),
):
    """Create a new email template (admin only)."""
    try:
        return create_email_template(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-templates")
def list_templates(_admin=Depends(get_current_admin)):
    """List all email templates (admin only)."""
    try:
        return list_email_templates()
    except ValueError as e:
        logger.warning("[list_templates] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-templates/{template_id}")
def get_template(template_id: str, _admin=Depends(get_current_admin)):
    """Get a specific email template by ID (admin only)."""
    try:
        return get_email_template(template_id)
    except ValueError as e:
        logger.warning("[get_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.put("/admin/email-templates/{template_id}")
def update_template_endpoint(
    template_id: str,
    payload: EmailTemplateUpdate,
    _admin=Depends(get_current_admin),
):
    """Update an email template (admin only)."""
    try:
        return update_email_template(
            template_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        logger.warning("[update_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.delete("/admin/email-templates/{template_id}")
def delete_template_endpoint(template_id: str, _admin=Depends(get_current_admin)):
    """Delete an email template (admin only). The default 'Resume Template' cannot be deleted."""
    try:
        return delete_email_template(template_id)
    except ValueError as e:
        logger.warning("[delete_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
