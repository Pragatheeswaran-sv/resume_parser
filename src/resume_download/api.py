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

from src.resume_download.schemas import MultiDownloadItem, MultiDownloadRequest
from src.email_reader.models import Attachment
from src.resume_filter.models import Resume
from src.admin.dependencies import get_current_admin_or_user
# from src.resume_download.schemas import (
#     MultiDownloadRequest,
#     MultiDownloadResponse,
#     MultiDownloadItem,
# )
# from src.services.resume_download.service import (
#     download_resume,
#     multi_download_urls,
#     # preview_resume,
# )

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

# from fastapi import APIRouter, HTTPException
# from fastapi.responses import FileResponse, StreamingResponse
# from typing import List

# from src.services.resume_download.service import (
#     # create_zip_and_save,
#     get_file_base64,
#     get_file_for_download,
#     # create_zip
# )
from db.connection import SessionLocal


# 🔹 1. Preview API (Base64)
# @router.get("/resume_preview/")
# def preview_file(resume_id):
#     try:
#         return get_file_base64(resume_id)
#     except FileNotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))

# # 🔹 2. Single Download API
# @router.get("/download/{filename}")
# def download_file(filename: str):
#     try:
#         file_path = get_file_for_download(filename)
#         return FileResponse(
#             path=file_path,
#             filename=filename,
#             media_type="application/octet-stream"
#         )
#     except FileNotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))


# 🔹 3. Multiple Download API (ZIP)
# @router.post("/download-multiple")
# def download_multiple(resume_ids : List):
#     try:
#         db = SessionLocal()
#         files = []
#         if not resume_ids:
#             return Exception('resume IDs missing')
        
#         for resume_id in resume_ids:
#             resume_details = db.query(Resume).filter_by(resume_id = resume_id).first()
#             attachment_id = resume_details.attachment_id

#             if not attachment_id:
#                 raise Exception('attachment not found')
            
#             Attachment_details = db.query(Attachment).filter_by(attachment_id = attachment_id).first()
#             files.append(Attachment_details.file_name)
#         zip_buffer = create_zip(files)

#         return StreamingResponse(
#             zip_buffer,
#             media_type="application/zip",
#             headers={
#                 "Content-Disposition": "attachment; filename=files.zip"
#             }
#         )
#     except FileNotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import os

from db.connection import SessionLocal
# from src.resume_download.schema import MultiDownloadRequest
from src.services.resume_download.service import get_download_links


BASE_DIR = "/app"   # inside docker
UPLOAD_DIR = os.path.join(BASE_DIR, "attachments")

# ✅ 1. Get download links (no zip)
@router.post("/download-multiple")
def download_multiple(
    request: MultiDownloadRequest,
):
    db = SessionLocal()
    files = get_download_links(db, request.resume_ids)

    return {
        "files": files
    }


# ✅ 2. Actual download endpoint (auto download)
@router.get("/download/{file_name}")
def download_file(file_name: str):
    file_path = os.path.join(UPLOAD_DIR, file_name)

    # 👇 ADD THIS LINE
    print("Checking file:", file_path)

    if not os.path.exists(file_path):
        print("File NOT found!")  # optional but helpful
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
    path=file_path,
    filename=file_name,
    media_type="application/octet-stream",
    headers={
        "Content-Disposition": f"attachment; filename={file_name}"
    }
)
# @router.post("/download-multiple")
# def download_multiple(resume_ids: MultiDownloadRequest):
#     try:
#         zip_name = create_zip_and_save(resume_ids)

#         return {
#             "download_url": f"/downloads/{zip_name}"
#         }

#     except FileNotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))