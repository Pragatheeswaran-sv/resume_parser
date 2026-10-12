"""API route endpoints for email reading and attachment processing.

All routes cleanly delegate to email_reader_service class methods,
maintaining complete separation between routing and business logic.
"""

import logging
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status

from src.email_reader.service import email_reader_service
from src.utils.response import serialize_response

load_dotenv()
logger = logging.getLogger(__name__)

# Legacy module-level alias for backward compatibility
fetch_emails = email_reader_service.fetch_emails

router = APIRouter(
    prefix="/api",
    tags=["Email-Reader"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/fetch_email", status_code=status.HTTP_200_OK)
def fetch_email() -> Dict[str, Any]:
    """Fetch new emails and process attachments."""
    try:
        data = email_reader_service.fetch_emails()
        return {"status": "success", "data": serialize_response(data)}
    except Exception as e:
        logger.error("Failed to process emails: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to process emails",
            },
        )
