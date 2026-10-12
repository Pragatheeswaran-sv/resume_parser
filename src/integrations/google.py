import base64
from datetime import datetime, timedelta
from email.utils import parseaddr
import logging
import os
from typing import Any, Dict
from urllib.parse import urlencode
import uuid

from dotenv import load_dotenv
from fastapi import HTTPException, status
import requests

from db.connection import SessionLocal
from src.admin.models import Users
from src.auth.jwt import create_access_token
from src.auth.models import OauthCredentials, OauthSource
from src.celery.tasks import resume_track
from src.email_reader.models import Attachment, EmailLogs

load_dotenv()
logger = logging.getLogger(__name__)

AUTH_URL = os.getenv("GMAIL_AUTH_URL")
TOKEN_URL = os.getenv("GMAIL_TOKEN_URL")
CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI")
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class GoogleIntegrationService:
    """Service class for Google/Gmail OAuth and email ingestion."""

    def gmail_login(self) -> Dict[str, Any]:
        try:
            params = {
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
                "access_type": "offline",
                "prompt": "consent",
            }

            url = f"{AUTH_URL}?{urlencode(params)}"
            logger.info(f"the url is: {url}")
            return {
                "status": "success",
                "auth_url": url,
            }
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Error generating auth URL"},
            )

    def gmail_callback(self, code: str, db=None) -> dict:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            logger.info(f"Received auth code {code}")

            token_data = {
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            }

            token_res = requests.post(TOKEN_URL, data=token_data)
            if token_res.status_code != 200:
                logger.error(f"Google Token Error: {token_res.text}")
            token_res.raise_for_status()

            tokens = token_res.json()

            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in")

            if not access_token:
                logger.error(f"Token response invalid: {tokens}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get access token",
                )

            profile_res = requests.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_res.raise_for_status()

            profile_data = profile_res.json()
            email = profile_data.get("emailAddress")

            if not email:
                logger.error(f"User info response invalid: {profile_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"status": "400", "message": "Unable to fetch user email"},
                )

            logger.info(f"OAuth login success for email: {email}")

            source = (
                db.query(OauthSource)
                .filter(OauthSource.source_name == "gmail")
                .first()
            )

            if not source:
                logger.info("Creating new Gmail source entry")
                source = OauthSource(source_name="gmail", created_by=email)
                db.add(source)
                db.commit()
                db.refresh(source)

            existing_cred = (
                db.query(OauthCredentials)
                .filter(
                    OauthCredentials.email == email,
                    OauthCredentials.source_id == source.source_id,
                )
                .first()
            )

            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            if existing_cred:
                logger.info(f"Updating existing credentials for {email}")
                existing_cred.access_token = access_token
                if refresh_token:
                    existing_cred.refresh_token = refresh_token
                existing_cred.expires_in = expires_in
                existing_cred.updated_by = email
            else:
                logger.info(f"Creating new credentials for {email}")
                new_cred = OauthCredentials(
                    email=email,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                    source_id=source.source_id,
                    created_by=email,
                )
                db.add(new_cred)

            db.commit()
            logger.info(
                f"Credentials stored for {email}, expires at {expires_at.isoformat()}"
            )

            valid_mail = (
                db.query(Users)
                .filter(
                    Users.email_address == email,
                    Users.is_blocked == False,
                    Users.is_active == True,
                )
                .first()
            )

            if not valid_mail:
                logger.warning(f"Email {email} is not authorized to connect")
                raise HTTPException(
                    status_code=status.HTTP_200_OK,
                    detail={
                        "status": status.HTTP_401_UNAUTHORIZED,
                        "message": "Email not authorized",
                    },
                )

            jwt_token = create_access_token(
                {"email": email, "sub": str(valid_mail.user_id), "role": "user"}
            )

            return {
                "status": status.HTTP_200_OK,
                "message": "OAuth connected successfully",
                "data": {
                    "name": valid_mail.name,
                    "email": email,
                    "access_token": jwt_token,
                    "is_admin": False,
                },
            }

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error during OAuth: {str(http_err)}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "OAuth provider error"},
            )

        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request error: {str(req_err)}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": "Network error during OAuth"},
            )

        except HTTPException:
            db.rollback()
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": "Internal server error"},
            )

        finally:
            if close_db:
                db.close()

    def get_valid_access_token(self, email: str, db=None) -> str:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            logger.info(f"Fetching access token for {email}")
            email = email.strip()
            cred = (
                db.query(OauthCredentials)
                .filter(OauthCredentials.email == email)
                .first()
            )

            if not cred:
                logger.error(f"No credentials found for {email}")
                raise Exception("OAuth credentials not found")
            expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

            if datetime.utcnow() >= expires_at:
                logger.info(f"Access token expired for {email}, refreshing...")
                if not cred.refresh_token:
                    raise Exception("Refresh token missing")

                token_url = "https://oauth2.googleapis.com/token"

                data = {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "refresh_token": cred.refresh_token,
                    "grant_type": "refresh_token",
                }

                response = requests.post(token_url, data=data)
                response.raise_for_status()

                new_tokens = response.json()

                cred.access_token = new_tokens.get("access_token")
                cred.expires_in = new_tokens.get("expires_in")
                cred.updated_at = datetime.utcnow()

                db.commit()

                return cred.access_token

            return cred.access_token
        finally:
            if close_db:
                db.close()

    def save_attachment_bytes(self, file_bytes, filename):
        attachment_dir = os.getenv("ATTACHMENT_DIR", "attachments")

        if not os.path.exists(attachment_dir):
            os.makedirs(attachment_dir)

        _, ext = os.path.splitext(filename)

        unique_name = f"{uuid.uuid4()}{ext}"
        path = os.path.join(attachment_dir, unique_name)

        with open(path, "wb") as f:
            f.write(file_bytes)

        return unique_name, path

    def process_parts(self, payload, message_id, email_obj, access_token, db=None):
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            parts = payload.get("parts", [])

            for part in parts:
                filename = part.get("filename")
                mime_type = part.get("mimeType")
                if not filename:
                    continue

                if mime_type not in ALLOWED_MIME_TYPES:
                    logger.info(f"Skipping unsupported file: {filename} ({mime_type})")
                    continue

                body = part.get("body", {})
                attachment_id = body.get("attachmentId")
                if not attachment_id:
                    continue

                att_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}"
                headers = {"Authorization": f"Bearer {access_token}"}
                att_res = requests.get(att_url, headers=headers)
                att_data = att_res.json()
                file_data = att_data.get("data")

                if not file_data:
                    logger.info(f"Empty attachment for {filename}")
                    continue

                file_bytes = base64.urlsafe_b64decode(file_data)
                saved_filename, _path = self.save_attachment_bytes(file_bytes, filename)

                attachment = Attachment(
                    email_id=email_obj.email_id,
                    file_name=saved_filename,
                )
                db.add(attachment)
                db.commit()
        finally:
            if close_db:
                db.close()

    def fetch_emails_gmail(self, email_id: str) -> dict:
        db = SessionLocal()
        gmail_list_url = os.getenv(
            "GMAIL_LIST_URL", "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        )
        try:
            cred = (
                db.query(OauthCredentials)
                .filter(OauthCredentials.email == email_id.strip())
                .first()
            )

            if not cred:
                logger.error(f"No credentials found for {email_id}")
                return {"status": "error", "message": "Credentials not found"}

            access_token = self.get_valid_access_token(email_id, db)
            headers = {"Authorization": f"Bearer {access_token}"}

            query = "has:attachment"
            if cred.last_processed_at:
                ts = int(cred.last_processed_at.timestamp())
                query += f" after:{ts}"

            logger.info(f"Gmail Query: {query}")
            params = {"q": query}

            resp = requests.get(gmail_list_url, headers=headers, params=params)
            resp.raise_for_status()

            data = resp.json()
            messages = data.get("messages", [])
            if not messages:
                cred.last_processed_at = datetime.utcnow()
                db.commit()
                return {"status": "success", "message": "No new emails found"}

            processed_count = 0
            for msg in messages:
                message_id = msg["id"]
                existing = (
                    db.query(EmailLogs)
                    .filter(EmailLogs.message_id == message_id)
                    .first()
                )

                if existing:
                    continue
                msg_res = requests.get(f"{gmail_list_url}/{message_id}", headers=headers)
                msg_res.raise_for_status()

                msg_data = msg_res.json()
                payload = msg_data.get("payload", {})
                headers_list = payload.get("headers", [])

                subject = ""
                sender = ""

                for h in headers_list:
                    if h["name"] == "Subject":
                        subject = h["value"]
                    if h["name"] == "From":
                        sender = parseaddr(h["value"])[1]

                email_obj = EmailLogs(
                    message_id=message_id,
                    subject=subject,
                    sender=sender,
                    source_mail=email_id,
                )
                db.add(email_obj)
                db.commit()
                db.refresh(email_obj)

                self.process_parts(payload, message_id, email_obj, access_token, db)

                celery_task = resume_track.delay(str(email_obj.email_id))
                logger.info(f"Processed email: {subject}, task id: {celery_task.id}")
                processed_count += 1

            cred.last_processed_at = datetime.utcnow()
            db.commit()

            logger.info(f"Total emails processed for {email_id}: {processed_count}")
            return {
                "status": "success",
                "message": f"Gmail emails processed: {processed_count}",
                "processed_count": processed_count,
            }

        except Exception as e:
            logger.error(f"Error in fetch_emails_gmail: {str(e)}", exc_info=True)
            db.rollback()
            raise

        finally:
            db.close()


GoogleService = GoogleIntegrationService
google_service = GoogleIntegrationService()

# Backward-compatible function references
gmail_login = google_service.gmail_login
gmail_callback = google_service.gmail_callback
get_valid_access_token = google_service.get_valid_access_token
save_attachment_bytes = google_service.save_attachment_bytes
process_parts = google_service.process_parts
fetch_emails_gmail = google_service.fetch_emails_gmail