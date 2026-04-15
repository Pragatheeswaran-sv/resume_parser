from fastapi.responses import RedirectResponse
from fastapi import Request
import requests
import logging
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
import os
from urllib.parse import urlencode
from db.connection import SessionLocal
from src.email_reader.models import EmailLogs
from src.services.auth.gmail.service import gmail_login
from src.services.auth.gmail.service import gmail_callback
from src.services.auth.gmail.service import zoho_callback
from src.services.auth.gmail.service import fetch_emails_gmail
from src.services.auth.zoho.service import fetch_emails_zoho
from src.auth.schemas import EmailRequest, EmailFetchResponse, EmailFetchResult
from src.services.auth.zoho.service import zoho_login
from src.auth.models import OauthCredentials, OauthSource
from src.admin.models import Users

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

# GMAIL_AUTH_URL = os.getenv("GMAIL_AUTH_URL")
# GMAIL_TOKEN_URL = os.getenv("GMAIL_TOKEN_URL")
# GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
# GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
# GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI")

@router.get("/oauth/login/gmail")
def oauth_gmail_login() -> dict:
    """Initiate OAuth flow by redirecting user to Google's auth page."""
    try:
        response = gmail_login()
        return response
    except Exception as e:
        logger.error(f"Error occurred while initiating Gmail OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.get("/auth/gmail/callback")
def callback(code: str) -> dict:
    """Handle OAuth callback and exchange code for tokens."""

    try:
        response = gmail_callback(code)
        return response
    except Exception as e:
        logger.error(f"Error occurred while handling Gmail OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.get("/auth/zoho/callback")
def callback(code: str) -> dict:
    """Handle OAuth callback and exchange code for tokens."""

    try:
        response = zoho_callback(code)
        return response
    except Exception as e:
        logger.error(f"Error occurred while handling Zoho OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

@router.get("/oauth/login/zoho")
def oauth_zoho_login() -> dict:
    """Initiate OAuth flow by redirecting user to Zoho's auth page."""
    try:
        response = zoho_login()
        return response
    except Exception as e:
        logger.error(f"Error occurred while initiating Zoho OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )

# @router.post("/emails")
# def fetch_emails_oauth(request: EmailRequest) -> dict:
#     logger.info(f"NAV----> Fetching emails for email_id: {request.email_id}")
#     response = fetch_emails_gmail(email_id=request.email_id)
#     # response = fetch_emails_zoho(email_id=request.email_id)
#     return response

@router.post("/emails")
def fetch_emails_oauth() -> EmailFetchResponse:
    """
    Fetch emails from all active users based on OAuth source (Gmail / Zoho).

    This API performs the following steps:

    1. Retrieves all active email खात (accounts) from `Users`
    2. For each email:
        - Finds corresponding OAuth credentials from `OauthCredentials`
        - Determines the email provider using `OauthSource`
    3. Based on the provider:
        - Calls Gmail service if source is `gmail`
        - Calls Zoho service if source is `zoho`
    4. Aggregates results for all processed emails

    ### Returns:
    - message: Status of the operation
    - results: List of processed emails with provider and status

    ### Possible Errors:
    - 500: Internal server error
    """

    logger.info("NAV----> Fetching emails for all active users")
    db = SessionLocal()

    results = []

    try:
        # 1. Get all active email
        users = db.query(Users).filter(
            Users.is_active == True
        ).all()
        logger.info(f"NAV----> Found {len(users)} active email accounts")

        if not users:
            return EmailFetchResponse(
                message="No active email accounts found",
                results=[]
            )

        for mail in users:
            email_id = (mail.email_address or "").strip()

            if not email_id:
                logger.warning("Empty email found, skipping...")
                continue

            logger.info(f"Processing email: {email_id}")

            # 2. Fetch OAuth credentials
            cred = db.query(OauthCredentials).filter(
                OauthCredentials.email == email_id,
                OauthCredentials.is_active == True
            ).first()

            if not cred:
                logger.warning(f"No OAuth credentials found for {email_id}")
                continue

            if not cred.source:
                logger.warning(f"No source mapped for {email_id}")
                continue

            # 3. Identify source
            source_name = cred.source.source_name.lower().strip()

            logger.info(f"Source detected: {source_name}")

            # 4. Call respective service
            try:
                if source_name == "gmail":
                    service_response = fetch_emails_gmail(email_id=email_id)

                elif source_name == "zoho":
                    service_response = fetch_emails_zoho(email_id=email_id)

                else:
                    logger.warning(f"Unsupported source: {source_name}")
                    continue

                status = "success"

            except Exception as service_error:
                logger.error(f"Error processing {email_id}: {str(service_error)}")
                status = f"failed: {str(service_error)}"

            results.append(
                EmailFetchResult(
                    email=email_id,
                    source=source_name,
                    status=status
                )
            )

        return EmailFetchResponse(
            message="Email fetching completed",
            results=results
        )

    except Exception as e:
        logger.error(f"Fatal error in fetch_emails_oauth: {str(e)}")
        raise HTTPException(
            status_code= 500,
            detail={"status": "error", "message": str(e)},
        )

