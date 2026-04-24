"""File-type detection and DOCX-to-PDF conversion utilities.

Uses LibreOffice in headless mode for reliable DOCX → PDF conversion.
Converted files are cached in a sibling ``converted/`` directory to
avoid repeated conversions of the same source file.
"""

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")
CONVERTED_CACHE_DIR = os.path.join(ATTACHMENT_DIR, "converted")

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def detect_file_type(file_name: str) -> str:
    """Return ``'pdf'``, ``'docx'``, or ``'unknown'`` based on file extension."""
    ext = Path(file_name).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    return "unknown"


def content_type_for(file_type: str) -> str:
    if file_type == "pdf":
        return PDF_CONTENT_TYPE
    if file_type == "docx":
        return DOCX_CONTENT_TYPE
    return "application/octet-stream"


def _cache_key(source_path: str) -> str:
    """Deterministic cache filename derived from the source path + mtime."""
    stat = os.stat(source_path)
    raw = f"{source_path}:{stat.st_mtime}:{stat.st_size}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    stem = Path(source_path).stem
    return f"{stem}_{digest}.pdf"


def _ensure_cache_dir() -> None:
    os.makedirs(CONVERTED_CACHE_DIR, exist_ok=True)


def convert_docx_to_pdf(source_path: str) -> str:
    """Convert a DOCX file to PDF, returning the path to the resulting PDF.

    Results are cached under ``CONVERTED_CACHE_DIR`` so subsequent calls
    for the same (unchanged) file skip the conversion entirely.

    Raises ``RuntimeError`` when LibreOffice is unavailable or conversion fails.
    """
    _ensure_cache_dir()

    cached_name = _cache_key(source_path)
    cached_path = os.path.join(CONVERTED_CACHE_DIR, cached_name)

    if os.path.exists(cached_path):
        logger.info("Using cached PDF: %s", cached_path)
        return cached_path

    lo_bin = _find_libreoffice()
    if lo_bin is None:
        raise RuntimeError(
            "LibreOffice is not installed. "
            "Install it (e.g. 'apt-get install libreoffice') "
            "or add it to PATH for DOCX→PDF conversion."
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_src = os.path.join(tmp_dir, Path(source_path).name)
        shutil.copy2(source_path, tmp_src)

        cmd = [
            lo_bin,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", tmp_dir,
            tmp_src,
        ]
        logger.info("Running LibreOffice conversion: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error("LibreOffice stderr: %s", result.stderr)
            raise RuntimeError(
                f"DOCX→PDF conversion failed (exit {result.returncode}): "
                f"{result.stderr[:500]}"
            )

        tmp_pdf = os.path.join(tmp_dir, Path(tmp_src).stem + ".pdf")
        if not os.path.exists(tmp_pdf):
            raise RuntimeError(
                "LibreOffice completed but output PDF was not found"
            )

        shutil.move(tmp_pdf, cached_path)

    logger.info("Converted and cached PDF: %s", cached_path)
    return cached_path


def _find_libreoffice() -> str | None:
    """Locate the LibreOffice binary on the system."""
    for name in ("libreoffice", "soffice", "libreoffice24.2"):
        path = shutil.which(name)
        if path:
            return path
    common_paths = [
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None
