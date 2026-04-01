import logging
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from src.services.email_reader.service import fetch_emails
from src.utils.response import serialize_response

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter(
	prefix="/api",
	tags=["Payment-Process"],
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
        data = fetch_emails()
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
