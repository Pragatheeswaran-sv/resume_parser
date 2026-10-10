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
from src.resume_download.schemas import MultiDownloadRequest, previewResumeRequest
from src.email_reader.models import Attachment
from src.resume_filter.models import Resume
from src.admin.dependencies import get_current_admin, get_current_admin_or_user
from db.connection import SessionLocal
from src.integrations.attachment_storage import (
    AttachmentStorageError,
    create_attachment_download_url,
    upload_attachment,
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
from src.resume_download.service import get_download_links, get_file_base64
BASE_DIR = "/app"   # inside docker
UPLOAD_DIR = os.path.join(BASE_DIR, "attachments")


@router.post("/admin/attachments/{attachment_id}/upload")
def upload_existing_attachment(
    attachment_id: UUID,
    expires_in: int = Query(default=3600, ge=60, le=604800),
    _admin=Depends(get_current_admin),
):
    """Upload one existing local attachment to Supabase Storage.

    The object keeps the attachment's existing ``file_name``.  That means no
    database update is needed: the current attachment/resume relationship keeps
    working and the returned signed URL can be used immediately for verification.
    """
    db = SessionLocal()
    try:
        attachment = db.query(Attachment).filter_by(attachment_id=attachment_id).first()
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment record not found")
        if not attachment.file_name:
            raise HTTPException(status_code=400, detail="Attachment has no filename")

        filename = os.path.basename(attachment.file_name)
        local_path = os.path.join(os.getenv("ATTACHMENT_DIR", "attachments"), filename)
        if not os.path.isfile(local_path):
            raise HTTPException(status_code=404, detail=f"Local attachment not found: {filename}")

        storage_key = upload_attachment(local_path, filename)
        prefix = os.getenv("SUPABASE_S3_PREFIX", "resumes").strip("/")
        return {
            "status": 200,
            "message": "Attachment uploaded to Supabase successfully",
            "data": {
                "attachment_id": str(attachment.attachment_id),
                "file_name": attachment.file_name,
                "storage_key": f"{prefix}/{storage_key}" if prefix else storage_key,
                "url": create_attachment_download_url(storage_key, expires_in),
                "url_expires_in": expires_in,
            },
        }
    except AttachmentStorageError as exc:
        logger.exception("Unable to upload existing attachment %s", attachment_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        db.close()

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
        files = get_download_links(db, request.candidate_ids)
        return files
    except Exception as e:
        logger.error(f"Error in download_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the download-multiple request")

# @router.get("/download/{file_name}")
# def download_file(file_name: str):
#     try:
#         file_path = os.path.join(UPLOAD_DIR, file_name)

#         logger.info("Checking file:", file_path)

#         if not os.path.exists(file_path):
#             logger.info("File NOT found!")  
#             raise HTTPException(status_code=404, detail="File not found")

#         return FileResponse(
#             path=file_path,
#             filename=file_name,
#             media_type="application/octet-stream",
#             headers={
#                 "Content-Disposition": f"attachment; filename={file_name}"
#             }
#         )
#     except Exception as e:
#         logger.error(f"Error in download_file: {str(e)}")
#         raise HTTPException(status_code=500, detail="An error occurred while processing the download_file request")
