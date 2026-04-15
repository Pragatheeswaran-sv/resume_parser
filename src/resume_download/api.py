"""Resume download and preview REST API router.

Endpoints
---------
GET  /api/resumes/{resume_id}/preview       – stream resume as PDF
GET  /api/resumes/{resume_id}/download      – download original or PDF
POST /api/resumes/multi-download            – batch download URL list
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from src.admin.dependencies import get_current_admin_or_user
from src.resume_download.schemas import (
    MultiDownloadRequest,
    MultiDownloadResponse,
    MultiDownloadItem,
)
from src.services.resume_download.service import (
    download_resume,
    multi_download_urls,
    preview_resume,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Resume-Download"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


# ── 1. Preview ────────────────────────────────────────────────────────────

@router.get("/resumes/{resume_id}/preview")
def resume_preview(
    resume_id: str,
    _caller=Depends(get_current_admin_or_user),
):
    """Stream the resume as a PDF.  DOCX files are converted on the fly."""
    try:
        file_path, content_type = preview_resume(resume_id)
        return FileResponse(
            path=file_path,
            media_type=content_type,
            headers={"Content-Type": content_type},
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": str(e)},
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": str(e)},
        )
    except RuntimeError as e:
        logger.error("Preview conversion failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to convert resume for preview",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in preview: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to generate preview"},
        )


# ── 2. Single download ───────────────────────────────────────────────────

@router.get("/resumes/{resume_id}/download")
def resume_download(
    resume_id: str,
    format: str = Query(default="original", pattern="^(pdf|original)$"),
    _caller=Depends(get_current_admin_or_user),
):
    """Download the resume file in the requested format."""
    try:
        file_path, content_type, filename = download_resume(resume_id, format)
        return FileResponse(
            path=file_path,
            media_type=content_type,
            filename=filename,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": str(e)},
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": str(e)},
        )
    except RuntimeError as e:
        logger.error("Download conversion failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to convert resume for download",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in download: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to download resume"},
        )


# ── 3. Multi download (URL list, no ZIP) ─────────────────────────────────

@router.post("/resumes/multi-download", response_model=MultiDownloadResponse)
def resume_multi_download(
    request: Request,
    body: MultiDownloadRequest,
    _caller=Depends(get_current_admin_or_user),
):
    """Return per-resume download URLs for the frontend to trigger individually."""
    base_url = str(request.base_url).rstrip("/")
    try:
        items = multi_download_urls(body.resumeIds, body.format, base_url)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "No valid resumes found for the given IDs",
                },
            )
        return MultiDownloadResponse(
            data=[MultiDownloadItem(**item) for item in items],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Multi-download error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to prepare multi-download",
            },
        )
