from datetime import datetime, timedelta
import logging
import os
from typing import Any, Dict
from urllib.parse import urlparse
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
from src.integrations.google import google_service

load_dotenv()
logger = logging.getLogger(__name__)

CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")
ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")
ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc")

ZOHO_OAUTH_ENDPOINTS = [
    "https://accounts.zoho.com/oauth/v2/token",
    "https://accounts.zoho.eu/oauth/v2/token",
    "https://accounts.zoho.com.au/oauth/v2/token",
    "https://accounts.zoho.jp/oauth/v2/token",
    "https://accounts.zohocloud.ca/oauth/v2/token",
    "https://accounts.zoho.sa/oauth/v2/token",
    "https://accounts.zoho.com.cn/oauth/v2/token",
    "https://accounts.zoho.in/oauth/v2/token",
]


class ZohoIntegrationService:
    """Service class for Zoho Mail OAuth and email ingestion."""

    def zoho_login(self) -> Dict[str, Any]:
        try:
            zoho_auth_base = "https://accounts.zoho.com"
            auth_url = (
                f"{zoho_auth_base}/oauth/v2/auth"
                f"?scope=ZohoMail.messages.ALL,ZohoMail.accounts.READ,ZohoMail.folders.READ"
                f"&client_id={CLIENT_ID}"
                f"&response_type=code"
                f"&access_type=offline"
                f"&prompt=consent"
                f"&redirect_uri={REDIRECT_URI}"
            )

            return {
                "status": "success",
                "auth_url": auth_url,
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": str(e)},
            )

    def get_mail_base_url(self, api_domain: str) -> str:
        return api_domain.replace("www.zohoapis", "mail.zoho") + "/api"

    def get_accounts_base_url(self, api_domain: str) -> str:
        return api_domain.replace("www.zohoapis", "accounts.zoho")

    def get_mail_api_base(self, api_domain: str) -> str:
        """Converts Zoho api_domain to the correct regional mail API base URL."""
        parsed = urlparse(api_domain)
        regional_suffix = parsed.netloc.replace("www.zohoapis.", "zoho.")
        return f"https://mail.{regional_suffix}/api"

    def get_zoho_accounts_token_url(self, api_domain: str) -> str:
        """Converts Zoho api_domain to the correct regional accounts OAuth token URL."""
        parsed = urlparse(api_domain)
        regional_suffix = parsed.netloc.replace("www.zohoapis.", "zoho.")
        return f"https://accounts.{regional_suffix}/oauth/v2/token"

    def process_oauth_zoho_token(
        self, token_data: Dict[str, str], db=None, timeout: int = 10
    ) -> Dict[str, Any] | None:
        """Exchanges a Zoho OAuth authorization/refresh token for access credentials."""
        for token_url in ZOHO_OAUTH_ENDPOINTS:
            try:
                logger.info(f"Requesting Zoho OAuth token from {token_url}")
                response = requests.post(token_url, data=token_data, timeout=timeout)
                response.raise_for_status()
                tokens = response.json()

                logger.info(f"Received Zoho token response from {token_url}: {tokens}")
                if tokens.get("access_token") or tokens.get("api_domain"):
                    logger.info(
                        "Zoho OAuth token retrieved successfully from %s", token_url
                    )
                    logger.debug("Zoho token response: %s", tokens)
                    return tokens

            except requests.RequestException as exc:
                logger.warning(
                    "Zoho OAuth request failed for %s: %s", token_url, exc
                )
                continue

        logger.error("Failed to retrieve Zoho OAuth token from all regions")
        return None

    def zoho_callback(self, code: str, db=None) -> dict:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            logger.info(f"Received Zoho callback with code: {code}")

            token_data = {
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            }

            tokens = self.process_oauth_zoho_token(token_data, db)
            logger.info(f"tokenssssss123: {tokens}")

            if not tokens:
                raise Exception("Invalid Zoho token response")

            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            api_domain = tokens.get("api_domain")
            expires_in = tokens.get("expires_in")
            logger.info(f"Zoho token response: {tokens}")
            logger.info(f"zoho_api_domain: {api_domain}")

            if not access_token or not api_domain:
                raise Exception("Invalid Zoho token response")

            base_url = self.get_mail_base_url(api_domain)
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

            logger.info(f"Base url for Zoho API: {base_url}")
            accounts_res = requests.get(f"{base_url}/accounts", headers=headers)
            accounts_res.raise_for_status()

            accounts_data = accounts_res.json()
            logger.info(f"Zoho accounts response: {accounts_data}")

            if not accounts_data.get("data") or not accounts_data["data"]:
                raise Exception("No account data returned from Zoho")

            email = accounts_data["data"][0].get("mailboxAddress")
            if not email:
                raise Exception("No mailboxAddress in Zoho account data")
            logger.info(f"Zoho account email: {email}")

            source = (
                db.query(OauthSource)
                .filter(OauthSource.source_name == "zoho")
                .first()
            )

            if not source:
                logger.info("Creating new Zoho source entry")
                source = OauthSource(source_name="zoho", created_by=email)
                db.add(source)
                db.commit()
                db.refresh(source)

            existing_cred = (
                db.query(OauthCredentials)
                .filter(OauthCredentials.email == email)
                .first()
            )

            if existing_cred:
                existing_cred.access_token = access_token
                existing_cred.refresh_token = refresh_token or existing_cred.refresh_token
                existing_cred.expires_in = expires_in
                existing_cred.api_domain = api_domain or existing_cred.api_domain
                existing_cred.updated_at = datetime.utcnow()
            else:
                new_cred = OauthCredentials(
                    email=email,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                    source_id=source.source_id,
                    api_domain=api_domain,
                    created_by=email,
                )
                db.add(new_cred)

            db.commit()

            valid_mail = (
                db.query(Users)
                .filter(
                    Users.is_blocked == False,
                    Users.email_address == email,
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

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500, detail={"status": "error", "message": str(e)}
            )

        finally:
            if close_db:
                db.close()

    def get_valid_zoho_token(self, email: str, db=None) -> str:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            logger.info(f"Fetching Zoho token for {email}")

            cred = (
                db.query(OauthCredentials)
                .filter(OauthCredentials.email == email)
                .first()
            )

            if not cred:
                raise Exception("Zoho credentials not found")

            expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

            if datetime.utcnow() >= expires_at:
                logger.info("Zoho token expired, refreshing...")

                token_url = self.get_zoho_accounts_token_url(cred.api_domain)

                payload = {
                    "refresh_token": cred.refresh_token,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "refresh_token",
                }

                res = requests.post(token_url, data=payload, timeout=10)
                res.raise_for_status()

                data = res.json()

                cred.access_token = data["access_token"]
                cred.expires_in = data["expires_in"]
                cred.updated_at = datetime.utcnow()

                db.commit()

            return cred.access_token
        finally:
            if close_db:
                db.close()

    def is_resume(self, filename: str) -> bool:
        return filename.lower().endswith(ALLOWED_EXTENSIONS)

    def save_attachment_bytes(self, file_bytes: bytes, filename: str):
        return google_service.save_attachment_bytes(file_bytes, filename)

    def get_account_id(self, api_domain: str, headers: dict) -> str:
        base = self.get_mail_api_base(api_domain)
        res = requests.get(f"{base}/accounts", headers=headers, timeout=10)
        res.raise_for_status()
        return res.json()["data"][0]["accountId"]

    def get_folders(self, api_domain: str, account_id: str, headers: dict):
        base = self.get_mail_api_base(api_domain)
        res = requests.get(
            f"{base}/accounts/{account_id}/folders",
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()
        return res.json().get("data", [])

    def get_messages(
        self, api_domain: str, account_id: str, folder_id: str, headers: dict
    ):
        base = self.get_mail_api_base(api_domain)
        res = requests.get(
            f"{base}/accounts/{account_id}/messages/view",
            headers=headers,
            params={"folderId": folder_id, "limit": 10},
            timeout=10,
        )
        res.raise_for_status()
        return res.json().get("data", [])

    def get_attachments(
        self,
        api_domain: str,
        account_id: str,
        folder_id: str,
        message_id: str,
        headers: dict,
    ):
        base = self.get_mail_api_base(api_domain)
        res = requests.get(
            f"{base}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachmentinfo",
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()
        return res.json().get("data", {}).get("attachments", [])

    def download_attachment(
        self,
        api_domain: str,
        account_id: str,
        folder_id: str,
        message_id: str,
        attachment: dict,
        headers: dict,
    ):
        base = self.get_mail_api_base(api_domain)
        attachment_id = attachment["attachmentId"]
        filename = attachment["attachmentName"]

        res = requests.get(
            f"{base}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachments/{attachment_id}",
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()

        return self.save_attachment_bytes(res.content, filename)

    def fetch_emails_zoho(self, email_id: str) -> dict:
        db = SessionLocal()
        try:
            cred = (
                db.query(OauthCredentials)
                .filter(OauthCredentials.email == email_id)
                .first()
            )

            if not cred:
                raise Exception("Zoho credentials not found")

            access_token = self.get_valid_zoho_token(email_id, db)
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            api_domain = cred.api_domain

            account_id = self.get_account_id(api_domain, headers)
            folders = self.get_folders(api_domain, account_id, headers)

            inbox_id = next(
                (f["folderId"] for f in folders if f["folderName"].lower() == "inbox"),
                None,
            )

            if not inbox_id:
                raise Exception("Inbox not found")

            messages = self.get_messages(api_domain, account_id, inbox_id, headers)
            if not messages:
                cred.last_processed_at = datetime.utcnow()
                db.commit()
                return {"status": "success", "processed_count": 0, "message": "No new emails"}

            logger.info(f"Zoho messages response: {messages}")
            processed_count = 0

            for msg in messages:
                msg_id = msg["messageId"]
                logger.info(f"Processing Zoho email: {msg_id}")

                if db.query(EmailLogs).filter(EmailLogs.message_id == msg_id).first():
                    continue

                try:
                    email_log = EmailLogs(
                        message_id=msg_id,
                        subject=msg.get("subject", ""),
                        sender=msg.get("fromAddress", ""),
                        source_mail=email_id,
                    )
                    db.add(email_log)
                    db.commit()
                    db.refresh(email_log)

                except Exception as e:
                    db.rollback()
                    logger.warning(f"Duplicate message_id skipped: {msg_id}")
                    continue

                attachments = self.get_attachments(
                    api_domain, account_id, inbox_id, msg_id, headers
                )

                for att in attachments:
                    if not self.is_resume(att["attachmentName"]):
                        continue

                    filename, _path = self.download_attachment(
                        api_domain, account_id, inbox_id, msg_id, att, headers
                    )

                    db.add(
                        Attachment(email_id=email_log.email_id, file_name=filename)
                    )
                    db.commit()

                celery_task = resume_track.delay(str(email_log.email_id))
                logger.info(f"Processed email {email_log.subject}, task={celery_task.id}")
                processed_count += 1

            logger.info(f"Processed_mail zoho count for {email_id}: {processed_count}")

            cred.last_processed_at = datetime.utcnow()
            db.commit()

            return {"status": "success", "processed_count": processed_count}

        except Exception as e:
            db.rollback()
            logger.error("Zoho fetch error", exc_info=True)
            raise

        finally:
            db.close()


ZohoService = ZohoIntegrationService
zoho_service = ZohoIntegrationService()

# Backward-compatible function references
zoho_login = zoho_service.zoho_login
zoho_callback = zoho_service.zoho_callback
get_valid_zoho_token = zoho_service.get_valid_zoho_token
fetch_emails_zoho = zoho_service.fetch_emails_zoho
