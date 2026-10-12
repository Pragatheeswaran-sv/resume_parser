"""API route endpoints for candidate management.

All routes cleanly delegate to candidate_service class methods,
maintaining complete separation between routing and business logic.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.admin.dependencies import get_current_admin, get_current_admin_or_user
from src.candidate.schema import (
    MultiDownloadRequest,
    NLSearchResponse,
)
from src.candidate.service import candidate_service, CandidateServiceError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Candidates"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/candidates")
def get_candidates(
    filters: Optional[Dict[str, Any]] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Retrieve candidate information with optional filtering, sorting, and pagination."""
    try:
        return candidate_service.get_candidates(filters=filters, page=page, page_size=page_size)
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[get_candidates] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[get_candidates] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[get_candidates] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[get_candidates] Request execution finished.")


@router.get("/export_data/")
def export_data(
    search_id: str,
    page: int,
    page_size: int,
    export: bool = False,
    _current_admin_or_user=Depends(get_current_admin_or_user),
):
    """Export candidates matching a cached search session as base64-encoded CSV."""
    try:
        return candidate_service.export_candidate(
            search_id=search_id,
            page=page,
            page_size=page_size,
            export=export,
        )
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[export_data] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[export_data] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[export_data] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[export_data] Request execution finished.")


@router.get("/candidate_basic_info/")
def candidate_basic_info(
    filter_by: Optional[str] = None,
    filter_value: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
):
    """Retrieves basic information about active candidates."""
    try:
        return candidate_service.get_candidate_basic_info(
            filter_by=filter_by,
            filter_value=filter_value,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[candidate_basic_info] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[candidate_basic_info] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[candidate_basic_info] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[candidate_basic_info] Request execution finished.")


@router.post("/generate_dynamic_filters")
def generate_dynamic_filters(body: dict) -> Dict[str, Any]:
    """Generate structured filter payload from a natural-language recruiter query."""
    try:
        return candidate_service.generate_dynamic_filters(body=body)
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[generate_dynamic_filters] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[generate_dynamic_filters] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[generate_dynamic_filters] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[generate_dynamic_filters] Request execution finished.")


@router.post("/filter_resumes")
def filter_resumes(
    filters: dict,
    search_id: str,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    page: int = Query(default=1, ge=1, description="Page number (must be >= 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Results per page (1-100)"),
) -> dict:
    """Filter resumes stored in the database with pagination support."""
    try:
        return candidate_service.filter_resumes(
            filters=filters,
            search_id=search_id,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[filter_resumes] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[filter_resumes] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[filter_resumes] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[filter_resumes] Request execution finished.")


@router.post("/profile_search", response_model=NLSearchResponse)
def nl_search(body: dict) -> Dict[str, Any]:
    """Search candidates using a natural-language query."""
    try:
        return candidate_service.profile_search(body=body)
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[nl_search] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[nl_search] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[nl_search] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[nl_search] Request execution finished.")


@router.get("/filter_options")
def show_filter() -> Dict[str, Any]:
    """Fetch master data for filters: Roles, Education, Skills."""
    try:
        return candidate_service.get_filter_options()
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[show_filter] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[show_filter] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[show_filter] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[show_filter] Request execution finished.")


@router.post("/admin/attachments/{attachment_id}/upload")
def upload_existing_attachment(
    attachment_id: UUID,
    expires_in: int = Query(default=3600, ge=60, le=604800),
    _admin=Depends(get_current_admin),
):
    """Upload one existing local attachment to Supabase Storage."""
    try:
        return candidate_service.upload_attachment_to_storage(
            attachment_id=attachment_id,
            expires_in=expires_in,
        )
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[upload_existing_attachment] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[upload_existing_attachment] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[upload_existing_attachment] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[upload_existing_attachment] Request execution finished.")


@router.get("/resume_preview/")
def preview_file(
    resume_id: Optional[str] = None,
    _current_admin_or_user=Depends(get_current_admin_or_user),
):
    """Fetch attachment file content encoded in base64 for in-browser preview."""
    try:
        return candidate_service.preview_file(resume_id=resume_id)
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[preview_file] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[preview_file] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[preview_file] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[preview_file] Request execution finished.")


@router.post("/download-multiple")
def download_multiple(
    request: MultiDownloadRequest,
    _current_admin_or_user=Depends(get_current_admin_or_user),
):
    """Create a zip archive of resumes for specified candidates and return base64 payload."""
    try:
        return candidate_service.download_multiple_resumes(candidate_ids=request.candidate_ids)
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[download_multiple] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[download_multiple] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[download_multiple] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[download_multiple] Request execution finished.")


@router.post("/modify_resume")
def modify_resume(payload: Dict, resume_id: str):
    """Tailor candidate resume against JD and produce updated PDF or docx."""
    try:
        return candidate_service.modify_resume(payload=payload, resume_id=resume_id)
    except HTTPException:
        raise
    except CandidateServiceError as e:
        logger.warning("[modify_resume] Service error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail={"status": "error", "message": str(e)},
        )
    except ValueError as e:
        logger.warning("[modify_resume] Validation error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )
    except Exception as e:
        logger.error("[modify_resume] Unexpected error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    finally:
        logger.info("[modify_resume] Request execution finished.")