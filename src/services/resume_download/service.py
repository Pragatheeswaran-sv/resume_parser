"""Service layer for resume preview, download, and DOCX→PDF conversion.

All database access is confined to this module so that the API layer
stays thin.  Conversion results are cached on disk to avoid redundant
LibreOffice invocations.
"""

import logging
import os
import base64
import mimetypes
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, load_only
from db.connection import SessionLocal
from src.resume_download.schemas import MultiDownloadRequest
from src.email_reader.models import Attachment
from src.resume_filter.models import Resume
from src.candidate.models import Candidate
from fastapi import HTTPException  
logger = logging.getLogger(__name__)

BASE_DIR = "/app"  
UPLOAD_DIR = os.path.join(BASE_DIR, "attachments")
FILES_DIR = "attachments/"


def get_file_path(filename: str) -> str:
    try:
        path = os.path.join(FILES_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"{filename} not found")
        return path
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_file_path: {str(e)}")
        raise Exception("An error occurred while retrieving the file path")

def get_file_base64(resume_id) -> dict:
    try:
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
            file_path = os.path.join(FILES_DIR, filename)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{file_path} not found")
            return {
                "status": status.HTTP_200_OK,
                "message": "File previewed successfully",
                "data":
                    {
                        "name": filename,
                        "type": mime_type,
                        "content": file_path
                    }
                }

        return {
                "status": status.HTTP_200_OK,
                "message": "File previewed successfully",
                "data":
                    {
                        "name": filename,
                        "type": mime_type,
                        "content": encoded
                    }
                }
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_file_base64: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

def get_file_for_download(filename: str) -> str:
    try:
        return get_file_path(filename)
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_file_for_download: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))

def get_download_links(db: Session, resume_ids: List[str]) -> List[dict]:
    try:

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
        return {
                    "status": status.HTTP_200_OK,
                    "message": "File downloaded successfully",
                    "data": result
                    }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_download_links: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the download links request")