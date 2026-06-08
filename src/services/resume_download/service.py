"""Service layer for resume preview, download, and DOCX→PDF conversion.

All database access is confined to this module so that the API layer
stays thin.  Conversion results are cached on disk to avoid redundant
LibreOffice invocations.
"""

import datetime
import logging
import os
import base64
import mimetypes
import re
import uuid
import shutil
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
DOWNLOAD_FILES = 'downloads/'

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
            # file_path = os.path.join(FILES_DIR, filename)

            # if not os.path.exists(file_path):
            #     raise FileNotFoundError(f"{file_path} not found")
            # return {
            #     "status": status.HTTP_200_OK,
            #     "message": "File previewed successfully",
            #     "data":
            #         {
            #             "name": filename,
            #             "type": mime_type,
            #             "content": file_path
            #         }
            #     }

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


def get_download_links(db: Session, candidate_ids: list[str]):
    try:
        candidate_details = (
            db.query(
                Candidate.name,
                Candidate.candidate_id,
                Resume.resume_id,
                Attachment.attachment_id,
                Attachment.file_name,
            )
            .join(Resume, Candidate.candidate_id == Resume.candidate_id)
            .join(Attachment, Resume.attachment_id == Attachment.attachment_id)
            .filter(Resume.candidate_id.in_(candidate_ids))
            .all()
        )

        if not candidate_details:
            raise HTTPException(status_code=404, detail="No resumes found")

        
        folder_name = (
            f"{uuid.uuid4()}_"
            f"{datetime.datetime.now():%Y%m%d_%H%M%S}"
        )

        download_path = os.path.join(BASE_DIR, DOWNLOAD_FILES)
        os.makedirs(download_path, exist_ok=True)

        temp_folder = os.path.join(download_path, folder_name)
        os.makedirs(temp_folder, exist_ok=True)

        for resume in candidate_details:
            
            candidate_name = re.sub(
                r'[<>:"/\\|?*]',
                "_",
                resume.name or "Unknown_Candidate"
            )

            candidate_folder = os.path.join(temp_folder, candidate_name)
            os.makedirs(candidate_folder, exist_ok=True)

            source_file = os.path.join(
                UPLOAD_DIR,
                str(resume.file_name)
            )

            if not os.path.exists(source_file):
                logger.warning(
                    f"File not found for attachment_id "
                    f"{resume.attachment_id}: {source_file}"
                )
                continue

            
            destination_file = os.path.join(
                candidate_folder,
                f"{resume.attachment_id}_{resume.file_name}"
            )

            shutil.copy2(source_file, destination_file)

        
        zip_path = shutil.make_archive(
            temp_folder,
            "zip",
            temp_folder
        )

        shutil.rmtree(temp_folder, ignore_errors=True)

        with open(zip_path, "rb") as zip_file:
            zip_base64 = base64.b64encode(zip_file.read()).decode("utf-8")

        return {
            "file_name": os.path.basename(zip_path),
            "content": zip_base64
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        logger.exception("Error in get_download_links")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the download request"
        )