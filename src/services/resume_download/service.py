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

def get_resume_with_attachment(
    resume_id: str,
    db: Session,
) -> Tuple[Resume, Attachment]:
    """Load a resume and its linked attachment; raises ``LookupError`` if not found."""
    resume = (
        db.query(Resume)
        .options(load_only(
            Resume.resume_id, Resume.attachment_id,
            Resume.candidate_id, Resume.is_active,
        ))
        .filter(Resume.resume_id == resume_id, Resume.is_active.is_(True))
        .first()
    )
    if not resume:
        raise LookupError(f"Resume {resume_id} not found or inactive")

    attachment = (
        db.query(Attachment)
        .filter(Attachment.attachment_id == resume.attachment_id)
        .first()
    )
    if not attachment:
        raise LookupError(
            f"Attachment for resume {resume_id} not found in database"
        )
    return resume, attachment


def resolve_file_path(attachment: Attachment) -> str:
    """Return the absolute on-disk path for an attachment, verifying it exists."""
    file_path = os.path.join(ATTACHMENT_DIR, attachment.file_name)
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"Resume file not found on disk: {attachment.file_name}"
        )
    return file_path


def _candidate_display_name(db: Session, candidate_id) -> str:
    """Best-effort candidate name for Content-Disposition filenames."""
    if not candidate_id:
        return "resume"
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if candidate and candidate.name:
        safe = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_"
            for c in candidate.name
        ).strip().replace(" ", "_")
        return safe or "resume"
    return "resume"


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def preview_resume(resume_id: str) -> Tuple[str, str]:
    """Return ``(file_path, content_type)`` suitable for streaming a PDF preview.

    DOCX files are converted to PDF on the fly (with caching).
    """
    db = SessionLocal()
    try:
        resume, attachment = get_resume_with_attachment(resume_id, db)
        source_path = resolve_file_path(attachment)
        file_type = detect_file_type(attachment.file_name)

        if file_type == "pdf":
            return source_path, "application/pdf"

        if file_type == "docx":
            pdf_path = convert_docx_to_pdf(source_path)
            return pdf_path, "application/pdf"

        raise ValueError(
            f"Unsupported file type for preview: {attachment.file_name}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Download (single)
# ---------------------------------------------------------------------------

def download_resume(
    resume_id: str,
    fmt: str = "original",
) -> Tuple[str, str, str]:
    """Return ``(file_path, content_type, download_filename)`` for a single resume.

    *fmt* is ``'original'`` (return as-is) or ``'pdf'`` (convert DOCX first).
    """
    db = SessionLocal()
    try:
        resume, attachment = get_resume_with_attachment(resume_id, db)
        source_path = resolve_file_path(attachment)
        file_type = detect_file_type(attachment.file_name)
        display_name = _candidate_display_name(db, resume.candidate_id)

        if fmt == "pdf" and file_type == "docx":
            pdf_path = convert_docx_to_pdf(source_path)
            return pdf_path, "application/pdf", f"{display_name}_resume.pdf"

        ct = content_type_for(file_type)
        ext = Path(attachment.file_name).suffix
        return source_path, ct, f"{display_name}_resume{ext}"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Multi-download (URL list – no ZIP)
# ---------------------------------------------------------------------------

def multi_download_urls(
    resume_ids: List[str],
    fmt: str = "original",
    base_url: str = "",
) -> List[dict]:
    """Validate that each resume exists and return per-resume download URLs.

    The actual file transfer is handled by the single-download endpoint;
    this helper only validates access and builds the URL list.
    """
    db = SessionLocal()
    try:
        results: List[dict] = []
        for rid in resume_ids:
            resume = (
                db.query(Resume)
                .options(load_only(Resume.resume_id, Resume.is_active))
                .filter(Resume.resume_id == rid, Resume.is_active.is_(True))
                .first()
            )
            if not resume:
                logger.warning("Multi-download: resume %s not found, skipping", rid)
                continue

            path = f"/api/resumes/{rid}/download"
            if fmt and fmt != "original":
                path += f"?format={fmt}"
            results.append({"resumeId": str(rid), "downloadUrl": f"{base_url}{path}"})
        return results
    finally:
        db.close()
