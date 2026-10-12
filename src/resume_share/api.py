import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.dependencies import get_current_admin
from src.resume_share.schemas import (
    RetryShareEmailRequest,
    RetryShareEmailResponse,
    ShareResumeRequest,
    ShareResumeResponse,
    EmailProviderConfigCreate,
    EmailProviderConfigUpdate,
    EmailTemplateCreate,
    EmailTemplateUpdate,
)
from src.resume_share.service import (
    ResumeShareError,
    ResumeShareService,
    resume_share_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Resume-Share"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


# ═══════════════════════════════════════════════════════════════════════════
#  Resume Share Routes
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/resume/share-email", response_model=ShareResumeResponse)
def share_resume_email(request: ShareResumeRequest):
    """Send a candidate's resume and profile details via email."""
    try:
        return resume_share_service.share_resume_email(
            candidate_id=request.candidate_id,
            resume_id=request.resume_id,
            to_address=request.to_address,
            cc_address=request.cc_address,
            share=request.share,
        )
    except ResumeShareError as e:
        logger.warning("Resume share error: %s (status=%d)", e.message, e.status_code)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(
            "Unexpected error in share_resume_email: %s", str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while sending the email",
        )


@router.post("/resume/share-email/retry", response_model=RetryShareEmailResponse)
def retry_share_emails(request: RetryShareEmailRequest):
    """Manually retry multiple failed email shares after fixing configuration."""
    try:
        return resume_share_service.retry_share_emails(request.email_share_ids)
    except Exception as e:
        logger.error(
            "Unexpected error in retry_share_emails: %s", str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrying emails",
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Email Provider Config CRUD (Admin only)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/admin/email-provider-config", tags=["Email-Config"])
def create_provider_config(
    payload: EmailProviderConfigCreate,
    _admin=Depends(get_current_admin),
):
    """Create a new email provider configuration (admin only)."""
    try:
        return resume_share_service.create_email_provider_config(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-provider-config", tags=["Email-Config"])
def list_provider_configs(
    page: int = 1,
    page_size: int = 10,
    filter_column: Optional[str] = None,
    filter_by: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    _admin=Depends(get_current_admin),
):
    """List all email provider configurations (admin only)."""
    try:
        return resume_share_service.list_email_provider_configs(
            int(page),
            int(page_size),
            filter_column,
            filter_by,
            sort_by,
            sort_order,
        )
    except ValueError as e:
        logger.warning("[list_provider_configs] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-provider-config/{config_id}", tags=["Email-Config"])
def get_provider_config(config_id: str, _admin=Depends(get_current_admin)):
    """Get a specific email provider configuration by ID (admin only)."""
    try:
        return resume_share_service.get_email_provider_config(config_id)
    except ValueError as e:
        logger.warning("[get_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.put("/admin/email-provider-config/{config_id}", tags=["Email-Config"])
def update_provider_config(
    config_id: str,
    payload: EmailProviderConfigUpdate,
    _admin=Depends(get_current_admin),
):
    """Update an email provider configuration (admin only)."""
    try:
        return resume_share_service.update_email_provider_config(
            config_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        logger.warning("[update_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.delete("/admin/email-provider-config/{config_id}", tags=["Email-Config"])
def delete_provider_config(config_id: str, _admin=Depends(get_current_admin)):
    """Delete an email provider configuration (admin only)."""
    try:
        return resume_share_service.delete_email_provider_config(config_id)
    except ValueError as e:
        logger.warning("[delete_provider_config] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Email Template CRUD (Admin only)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/admin/email-templates", tags=["Email-Config"])
def create_template(
    payload: EmailTemplateCreate,
    _admin=Depends(get_current_admin),
):
    """Create a new email template (admin only)."""
    try:
        return resume_share_service.create_email_template(payload.model_dump())
    except ValueError as e:
        logger.warning("[create_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-templates", tags=["Email-Config"])
def list_templates(_admin=Depends(get_current_admin)):
    """List all email templates (admin only)."""
    try:
        return resume_share_service.list_email_templates()
    except ValueError as e:
        logger.warning("[list_templates] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/admin/email-templates/{template_id}", tags=["Email-Config"])
def get_template(template_id: str, _admin=Depends(get_current_admin)):
    """Get a specific email template by ID (admin only)."""
    try:
        return resume_share_service.get_email_template(template_id)
    except ValueError as e:
        logger.warning("[get_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.put("/admin/email-templates/{template_id}", tags=["Email-Config"])
def update_template_endpoint(
    template_id: str,
    payload: EmailTemplateUpdate,
    _admin=Depends(get_current_admin),
):
    """Update an email template (admin only)."""
    try:
        return resume_share_service.update_email_template(
            template_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        logger.warning("[update_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.delete("/admin/email-templates/{template_id}", tags=["Email-Config"])
def delete_template_endpoint(template_id: str, _admin=Depends(get_current_admin)):
    """Delete an email template (admin only)."""
    try:
        return resume_share_service.delete_email_template(template_id)
    except ValueError as e:
        logger.warning("[delete_template] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
