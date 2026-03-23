import os
import json
import logging
from dotenv import load_dotenv
from fastapi import APIRouter
from typing import List, Dict, Any
from src.services.email_reader.service import fetch_emails
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

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

# @router.post("/fetch_email")
# def fetch_email():
#     """Fetch new emails and process attachments."""
    
#     response = fetch_emails()
#     return response


@router.post("/fetch_email", status_code=status.HTTP_200_OK)
def fetch_email():
    """Fetch new emails and process attachments."""
    
    try:
        data = fetch_emails()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Emails fetched and processed successfully",
                "data": data
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to process emails",
                "error": str(e)
            }
        )