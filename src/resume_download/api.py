"""Resume download and preview REST API router.

Endpoints
---------
GET  /api/resumes/{resume_id}/preview       – stream resume as PDF
GET  /api/resumes/{resume_id}/download      – download original or PDF
POST /api/resumes/multi-download            – batch download URL list
"""
import os
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from src.resume_download.schemas import MultiDownloadItem, MultiDownloadRequest, previewResumeRequest
from src.email_reader.models import Attachment
from src.resume_filter.models import Resume
from src.admin.dependencies import get_current_admin_or_user
from db.connection import SessionLocal

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

from src.services.resume_download.service import get_download_links, get_file_base64

BASE_DIR = "/app"   # inside docker
UPLOAD_DIR = os.path.join(BASE_DIR, "attachments")

@router.get("/resume_preview/")
def preview_file(resume_id : str | None = None, _current_admin_or_user = Depends(get_current_admin_or_user)):
    try:
        if resume_id.strip() == "" or resume_id == None:
            raise HTTPException(status_code=400, detail="Resume ID is required")
        return get_file_base64(resume_id)
    except HTTPException:
        raise

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Error in preview_file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/download-multiple")
def download_multiple(
    request: MultiDownloadRequest,
    _current_admin_or_user = Depends(get_current_admin_or_user)
):
    try: 
        db = SessionLocal()
        files = get_download_links(db, request.resume_ids)
        return files
    except Exception as e:
        logger.error(f"Error in download_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the download-multiple request")

@router.get("/download/{file_name}")
def download_file(file_name: str):
    try:
        file_path = os.path.join(UPLOAD_DIR, file_name)

        print("Checking file:", file_path)

        if not os.path.exists(file_path):
            print("File NOT found!")  
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={file_name}"
            }
        )
    except Exception as e:
        logger.error(f"Error in download_file: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the download_file request")