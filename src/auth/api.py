from fastapi.responses import RedirectResponse
from fastapi import Request, Depends
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
# from src.services.auth.gmail.service import zoho_callback
from src.services.auth.zoho.service import zoho_callback
from src.services.auth.gmail.service import fetch_emails_gmail
from src.services.auth.zoho.service import fetch_emails_zoho
from src.auth.schemas import EmailRequest, EmailFetchResponse
from src.services.auth.zoho.service import zoho_login
from src.auth.models import OauthCredentials, OauthSource
from src.admin.models import Users
from src.services.auth.service import fetch_emails_oauth
from src.services.auth.service import fetch_oauth_email_by_id
from src.auth.schemas import EmailFetchResult
from src.services.auth.logout_service import logout_user
from src.auth.jwt import decode_access_token
from jose import JWTError
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
def fetch_oauth_emails() -> EmailFetchResponse:
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

    ### Request Body (optional):
    - emails: Single email or comma-separated emails (e.g., "a@gmail.com,b@zoho.com")
      If not provided, fetches for all active users.

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
        emails_param = request.emails if request else None
        respone = fetch_emails_oauth(emails=emails_param)
        return respone
    except Exception as e:
        logger.error(f"Error occurred while initiating Zoho OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e)},
        )


from pydantic import BaseModel, EmailStr


@router.post("/emails/process")
def process_single_email(request: EmailRequest) -> dict:
    """
    Fetch emails for a specific email address.
    
    This endpoint processes emails for a single user by their email address.
    
    ### Request Body:
    - email: The email address to fetch emails for (e.g., "user@domain.com")
    
    ### Returns:
    - status: "success" or "error"
    - message: Status message
    - source: Email provider (gmail/zoho)
    - processed_count: Number of emails processed
    
    ### Validations:
    - Email must be registered and active in Users table
    - OAuth credentials must exist for the email
    - Source must be gmail or zoho
    
    ### Possible Errors:
    - 400: Invalid email, user not found, or no OAuth credentials
    - 500: Internal server error
    """
    logger.info(f"NAV----> Processing email: {request.email_id}")
    
    result = fetch_oauth_email_by_id(email_id=request.email_id)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


@router.post("/auth/logout")
def logout_endpoint(request: Request) -> dict:
    """
    Generic logout endpoint that revokes OAuth tokens across all providers.
    
    This endpoint:
    1. Extracts user email from JWT token
    2. Finds user's OAuth credentials
    3. Revokes tokens with the appropriate provider (Gmail/Zoho)
    4. Deletes credentials from database
    
    ### Headers:
    - Authorization: Bearer <JWT_TOKEN>
    
    ### Returns:
    - Status of logout operation and providers that were revoked
    
    ### Errors:
    - 401: Missing or invalid authorization header
    - 500: Server error during logout
    """
    try:
        # Extract JWT from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Missing or invalid Authorization header"}
            )
        
        token = auth_header.split(" ")[1]
        
        # Decode token to get email
        try:
            payload = decode_access_token(token)
            email = payload.get("email")  # Standard JWT email claim
            
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"status": "error", "message": "Token missing email claim"}
                )
        except JWTError as e:
            logger.error(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Invalid or expired token"}
            )
        
        # Perform logout
        logger.info(f"Logout request for email: {email}")
        result = logout_user(email)
        
        if result["status"] == "success":
            return {
                "status": status.HTTP_200_OK,
                "message": "Logout successful",
                "data": result.get("data", {})
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": result.get("message", "Logout failed")}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in logout endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)}
        )
