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
from src.services.auth.gmail.service import fetch_emails_gmail
from src.services.auth.zoho.service import fetch_emails_zoho
from src.auth.schemas import EmailRequest, EmailFetchResponse, EmailFetchResult
from src.auth.models import OauthCredentials, OauthSource
from src.admin.models import Users

load_dotenv()
logger = logging.getLogger(__name__)

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
            Users.is_blocked == False,
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

            service_response = service_response 
            results.append(
                EmailFetchResult(
                    email=email_id,
                    source=source_name,
                    status=status,
                    processed_count=service_response.get('processed_count', 0)
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


def fetch_oauth_email_by_id(email_id: str) -> dict:
    """
    Fetch emails for a specific email address.
    
    Args:
        email_id: The specific email address to fetch emails for.
        
    Returns:
        dict with status, message, source, processed_count
    """
    logger.info(f"NAV----> Fetching emails for specific email: {email_id}")
    db = SessionLocal()
    
    try:
        email_id = email_id.strip()
        
        if not email_id:
            return {
                "status": "error",
                "message": "Email address is required",
                "source": None,
                "processed_count": 0
            }
        
        # 1. Check if user exists in Users table
        user = db.query(Users).filter(
            Users.email_address == email_id,
            Users.is_blocked == False,
            Users.is_active == True
        ).first()
        
        if not user:
            return {
                "status": "error",
                "message": f"User with email '{email_id}' not found or inactive/ blocked",
                "source": None,
                "processed_count": 0
            }
        
        # 2. Fetch OAuth credentials
        cred = db.query(OauthCredentials).filter(
            OauthCredentials.email == email_id,
            OauthCredentials.is_active == True
        ).first()
        
        if not cred:
            return {
                "status": "error",
                "message": f"No OAuth credentials found for {email_id}. Please connect via OAuth first.",
                "source": None,
                "processed_count": 0
            }
        
        if not cred.source:
            return {
                "status": "error",
                "message": f"No OAuth source mapped for {email_id}",
                "source": None,
                "processed_count": 0
            }
        
        # 3. Identify source
        source_name = cred.source.source_name.lower().strip()
        logger.info(f"NAV----> Source detected: {source_name}")
        
        # 4. Update sync_status to "syncing"
        cred.sync_status = "syncing"
        db.commit()
        
        # 5. Call respective service
        try:
            if source_name == "gmail":
                service_response = fetch_emails_gmail(email_id=email_id)
            elif source_name == "zoho":
                service_response = fetch_emails_zoho(email_id=email_id)
            else:
                cred.sync_status = "failed"
                db.commit()
                return {
                    "status": "error",
                    "message": f"Unsupported source: {source_name}. Supported: gmail, zoho",
                    "source": source_name,
                    "processed_count": 0
                }
            
            # 6. Update sync_status to "completed" on success
            cred.sync_status = "completed"
            db.commit()
            
            return {
                "status": "success",
                "message": service_response.get("message", "Emails fetched successfully"),
                "source": source_name,
                "processed_count": service_response.get("processed_count", 0)
            }
            
        except Exception as service_error:
            logger.error(f"Error processing {email_id}: {str(service_error)}")
            cred.sync_status = "failed"
            db.commit()
            return {
                "status": "error",
                "message": f"Failed to process emails: {str(service_error)}",
                "source": source_name,
                "processed_count": 0
            }
    
    except Exception as e:
        logger.error(f"Fatal error in fetch_oauth_email_by_id: {str(e)}")
        if cred:
            cred.sync_status = "failed"
            db.commit()
        return {
            "status": "error",
            "message": str(e),
            "source": None,
            "processed_count": 0
        }
    finally:
        db.close()