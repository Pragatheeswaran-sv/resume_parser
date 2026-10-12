"""API route endpoints for authentication, OAuth callbacks, and token revocation.

All routes delegate cleanly to auth_service class methods,
maintaining complete separation between routing and business logic.
"""

import logging
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, status

from src.auth.schemas import EmailFetchResponse, EmailRequest
from src.auth.service import auth_service

load_dotenv()
logger = logging.getLogger(__name__)

# Legacy module-level aliases for backward compatibility
fetch_emails_oauth = auth_service.fetch_emails_oauth
fetch_oauth_email_by_id = auth_service.fetch_oauth_email_by_id
logout_user = auth_service.logout_user

router = APIRouter(
    prefix="/api",
    tags=["Auth"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)


@router.get("/oauth/login/gmail")
def oauth_gmail_login() -> Dict[str, Any]:
    """Initiate OAuth flow by redirecting user to Google's auth page."""
    try:
        return auth_service.gmail_login()
    except Exception as e:
        logger.error("Error occurred while initiating Gmail OAuth: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/auth/gmail/callback")
def gmail_callback(code: str) -> Dict[str, Any]:
    """Handle OAuth callback and exchange code for Google tokens."""
    try:
        return auth_service.gmail_callback(code)
    except Exception as e:
        logger.error("Error occurred while handling Gmail OAuth callback: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/oauth/login/zoho")
def oauth_zoho_login() -> Dict[str, Any]:
    """Initiate OAuth flow by redirecting user to Zoho's auth page."""
    try:
        return auth_service.zoho_login()
    except Exception as e:
        logger.error("Error occurred while initiating Zoho OAuth: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.get("/auth/zoho/callback")
def zoho_callback(code: str) -> Dict[str, Any]:
    """Handle OAuth callback and exchange code for Zoho tokens."""
    try:
        return auth_service.zoho_callback(code)
    except Exception as e:
        logger.error("Error occurred while handling Zoho OAuth callback: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/emails")
def fetch_oauth_emails() -> EmailFetchResponse:
    """Fetch emails from all active users based on OAuth source (Gmail / Zoho)."""
    try:
        return auth_service.fetch_emails_oauth()
    except Exception as e:
        logger.error("Error occurred while fetching emails: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


@router.post("/emails/process")
def process_single_email(request: EmailRequest) -> Dict[str, Any]:
    """Fetch emails for a specific email address."""
    result = auth_service.fetch_oauth_email_by_id(email_id=request.email_id)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    return result


@router.post("/auth/logout")
def logout_endpoint(request: Request) -> Dict[str, Any]:
    """Generic logout endpoint that revokes OAuth tokens across providers and updates session."""
    return auth_service.logout(request.headers.get("Authorization"))
