"""Service layer for resume preview, download, and DOCX→PDF conversion.

All database access is confined to this module so that the API layer
stays thin.  Conversion results are cached on disk to avoid redundant
LibreOffice invocations.
"""

import logging
import os
from pathlib import Path
from typing import List, Tuple

from sqlalchemy.orm import Session, load_only

from db.connection import SessionLocal
from src.resume_download.schemas import MultiDownloadRequest
from src.email_reader.models import Attachment
from src.resume_filter.models import Resume
from src.candidate.models import Candidate
from src.utils.file_conversion import (
    ATTACHMENT_DIR,
    convert_docx_to_pdf,
    content_type_for,
    detect_file_type,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resume fetching helpers
# ---------------------------------------------------------------------------

# 

import os
import base64
import mimetypes
import zipfile
from io import BytesIO
from typing import List

FILES_DIR = "attachments/"


def get_file_path(filename: str) -> str:
    path = os.path.join(FILES_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{filename} not found")
    return path


# 🔹 1. Preview (Base64)
def get_file_base64(resume_id) -> dict:
    db = SessionLocal()
    resume_details = db.query(Resume).filter_by(resume_id = resume_id).first()
    attachment_id = resume_details.attachment_id

    if not attachment_id:
        raise Exception('attachment not found')
    
    Attachment_details = db.query(Attachment).filter_by(attachment_id = attachment_id).first()
    filename = Attachment_details.file_name

    if not filename:
        raise Exception('file name not found')
    path = get_file_path(filename)

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type != 'application/pdf':
        mime_type = 'application/docx'
        
    return {
        "name": filename,
        "type": mime_type,
        "content": encoded
    }

def get_file_for_download(filename: str) -> str:
    return get_file_path(filename)

# 🔹 3. Multiple files → ZIP
# def create_zip(files: List[str]) -> BytesIO:
#     zip_buffer = BytesIO()

#     with zipfile.ZipFile(zip_buffer, "w") as zip_file:
#         for file in files:
#             path = get_file_path(file)
#             zip_file.write(path, arcname=file)

#     zip_buffer.seek(0)
#     return zip_buffer


import os
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.resume_filter.models import Resume, Attachment  # adjust import
# from src.config import settings  # if you have base URL config


BASE_DIR = "/app"   # inside docker
UPLOAD_DIR = os.path.join(BASE_DIR, "attachments") # folder where files are stored


def get_download_links(db: Session, resume_ids: List[str]) -> List[dict]:
    # ✅ fetch resumes in one query
    resumes = (
        db.query(Resume)
        .filter(Resume.resume_id.in_(resume_ids))
        .all()
    )

    if not resumes:
        raise HTTPException(status_code=404, detail="No resumes found")

    attachment_ids = [r.attachment_id for r in resumes if r.attachment_id]

    if not attachment_ids:
        raise HTTPException(status_code=404, detail="No attachments found")

    # ✅ fetch attachments
    attachments = (
        db.query(Attachment)
        .filter(Attachment.attachment_id.in_(attachment_ids))
        .all()
    )

    if not attachments:
        raise HTTPException(status_code=404, detail="No files found")

    result = []

    for att in attachments:
        file_name = att.file_name
        file_path = os.path.join(UPLOAD_DIR, file_name)

        if not os.path.exists(file_path):
            continue

        result.append({
            "file_name": file_name,
            "download_url": f"/attachments/{file_name}"
        })
    
    if not result:
        raise HTTPException(status_code=404, detail="Files not found on server")

    return result

# def create_zip_and_save(resume_ids) -> str:
#     db = SessionLocal()
#     files = []
#     for resume_id in resume_ids:
#         resume_details = db.query(Resume).filter_by(resume_id = resume_id).first()
#         attachment_id = resume_details.attachment_id

#         if not attachment_id:
#             raise Exception('attachment not found')
        
#         Attachment_details = db.query(Attachment).filter_by(attachment_id = attachment_id).first()
#         # return Attachment_details.file_name
#         files.append(Attachment_details.file_name)
#         return files
#     os.makedirs(DOWNLOAD_DIR, exist_ok=True)

#     # unique zip name
#     zip_name = f"resumes_{datetime.utcnow().timestamp()}.zip"
#     zip_path = os.path.join(DOWNLOAD_DIR, zip_name)

#     with zipfile.ZipFile(zip_path, "w") as zipf:
#         for file in files:
#             file_path = get_file_path(file)
#             zipf.write(file_path, arcname=file)

#     return zip_name