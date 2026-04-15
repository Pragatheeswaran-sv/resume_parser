from fastapi.responses import RedirectResponse
import requests
import logging
from dotenv import load_dotenv
from fastapi import Request, APIRouter, HTTPException, status
from typing import Dict, Any
import os
from urllib.parse import urlencode
from db.connection import SessionLocal
from datetime import datetime, timedelta
from src.email_reader.models import EmailLogs
from src.auth.models import OauthSource, OauthCredentials
from src.email_reader.models import Attachment
from src.services.background_task.tasks import resume_track
from src.services.auth.gmail.service import save_attachment_bytes
import base64


load_dotenv()
logger = logging.getLogger(__name__)

def get_valid_zoho_access_token(email: str, db=SessionLocal()):
    logger.info(f"NAV----> Fetching Zoho access token for {email}")
    email = email.strip()

    source = db.query(OauthSource).filter(
        OauthSource.source_name == "zoho"
    ).first()

    if not source:
        raise Exception("Zoho source not found")

    cred = db.query(OauthCredentials).filter(
        OauthCredentials.email == email,
        OauthCredentials.source_id == source.source_id
    ).first()

    if not cred:
        logger.error(f"No Zoho credentials found for {email}")
        raise Exception("Zoho OAuth credentials not found")

    expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

    if datetime.utcnow() >= expires_at:
        logger.info(f"NAV----> Zoho token expired for {email}, refreshing...")

        if not cred.refresh_token:
            raise Exception("Zoho refresh token missing")

        token_url = "https://accounts.zoho.in/oauth/v2/token"

        data = {
            "grant_type": "refresh_token",
            "client_id": os.getenv("ZOHO_CLIENT_ID"),
            "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
            "refresh_token": cred.refresh_token,
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

import email
from email import policy

# def process_zoho_attachments(account_id, message_id, email_obj, access_token, db):
#     try:
#         headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
#         ALLOWED_MIME_TYPES = {
#             "application/pdf",
#             "application/msword",
#             "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#             "application/octet-stream",  # fallback (handle with extension check)
#         }

#         att_res = requests.get(
#             f"https://mail.zoho.in/api/accounts/{account_id}/messages/{message_id}/attachments",
#             headers=headers
#         )
#         att_res.raise_for_status()

#         attachments = att_res.json().get("data", [])

#         for att in attachments:
#             try:
#                 filename = att.get("attachmentName")
#                 mime_type = att.get("contentType")
#                 attachment_id = att.get("attachmentId")

#                 if not filename:
#                     continue

#                 # 🔹 Filter file types
#                 if mime_type not in ALLOWED_MIME_TYPES:
#                     logger.info(f"Skipping unsupported file: {filename} ({mime_type})")
#                     continue

#                 # 🔹 Download file (binary)
#                 file_res = requests.get(
#                     f"https://mail.zoho.in/api/accounts/{account_id}/messages/{message_id}/attachments/{attachment_id}",
#                     headers=headers
#                 )
#                 file_res.raise_for_status()

#                 file_bytes = file_res.content

#                 filename, path = save_attachment_bytes(file_bytes, filename)

#                 attachment = Attachment(
#                     email_id=email_obj.email_id,
#                     file_name=filename,
#                 )
#                 db.add(attachment)
#                 db.commit()

#                 logger.info(f"Saved Zoho attachment: {filename}")

#             except Exception as e:
#                 logger.error(f"Zoho attachment error: {str(e)}", exc_info=True)
#                 continue

#     except Exception as e:
#         logger.error(f"Failed to fetch Zoho attachments: {str(e)}", exc_info=True)


# def fetch_emails_zoho(email_id: str) -> dict:
#     db = SessionLocal()

#     try:
#         # 🔹 Step 1: Get valid token
#         access_token = get_valid_zoho_access_token(email_id, db)

#         headers = {
#             "Authorization": f"Zoho-oauthtoken {access_token}"
#         }

#         # 🔹 Step 2: Get account ID
#         acc_res = requests.get(
#             "https://mail.zoho.in/api/accounts",
#             headers=headers
#         )
#         acc_res.raise_for_status()

#         accounts = acc_res.json().get("data", [])
#         if not accounts:
#             return {"message": "No Zoho account found"}

#         account_id = accounts[0]["accountId"]

#         # 🔹 Step 3: Fetch emails
#         mails_res = requests.get(
#             f"https://mail.zoho.in/api/accounts/{account_id}/messages/view",
#             headers=headers,
#             params={
#                 # "status": "unread",
#                 "limit": 10
#             }
#         )
#         mails_res.raise_for_status()

#         messages = mails_res.json().get("data", [])

#         if not messages:
#             return {"message": "No new emails"}

#         processed_count = 0

#         for mail in messages:
#             logger.info(f"NAV----> Raw mail object: {mail}")
#             # message_id = mail.get("messageId")
#             # message_id = mail.get("mailId") or mail.get("messageId")
#             message_id = mail.get("messageId")
#             folder_id = mail.get("folderId")

#             logger.info(f"NAV----> Processing Zoho email_latest: {message_id}")

#             # 🔹 Avoid duplicates
#             existing = db.query(EmailLogs).filter(
#                 EmailLogs.message_id == message_id
#             ).first()

#             if existing:
#                 continue

#             subject = mail.get("subject")
#             sender = mail.get("fromAddress")

#             # 🔹 Save email
#             email_obj = EmailLogs(
#                 message_id=message_id,
#                 subject=subject,
#                 sender=sender,
#             )
#             db.add(email_obj)
#             db.commit()
#             db.refresh(email_obj)

#             # 🔹 Process attachments
#             logger.info(f"NAV----> Fetching attachments for Zoho email: {message_id}")
#             files = process_zoho_attachments(
#                 account_id=account_id,
#                 folder_id=folder_id,
#                 message_id=message_id,
#                 headers=headers
#             )
#             logger.info(f"NAV----> Attachments saved: {files}")
#             # process_zoho_attachments(
#             #     account_id,
#             #     message_id,
#             #     folder_id,
#             #     email_obj,
#             #     access_token,
#             #     db
#             # )

#             # 🔹 (Optional) Mark as read → Zoho doesn’t support like Gmail directly
#             # You can skip or use flags API if needed

#             # 🔹 Celery trigger
#             celery_task = resume_track.delay(str(email_obj.email_id))

#             logger.info(f"Processed Zoho email: {subject}, task: {celery_task.id}")

#             processed_count += 1

#         return {
#             "message": "Zoho emails processed",
#             "processed_count": processed_count
#         }

#     except Exception as e:
#         logger.error(f"Error in fetch_emails_zoho: {str(e)}", exc_info=True)
#         db.rollback()
#         raise

#     finally:
#         db.close()

CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")
ATTACHMENT_DIR = "attachments"
BASE_URL = "https://mail.zoho.in/api"
ZOHO_AUTH_URL = "https://accounts.zoho.in/oauth/v2/auth"


def zoho_login():
    try:
        url = f"{ZOHO_AUTH_URL}?scope=ZohoMail.messages.ALL,ZohoMail.accounts.READ,ZohoMail.folders.READ&client_id={CLIENT_ID}&response_type=code&access_type=offline&prompt=consent&redirect_uri={REDIRECT_URI}"

        return {
                "status": "success",
                "auth_url": url
            }
    except Exception as e:
        logger.error(f"Error generating Zoho auth URL: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Error generating Zoho auth URL"})

def get_valid_zoho_token(email: str, db: SessionLocal()):
    logger.info(f"Fetching Zoho token for {email}")

    cred = db.query(OauthCredentials).filter(
        OauthCredentials.email == email
    ).first()

    if not cred:
        raise Exception("Zoho credentials not found")

    expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

    if datetime.utcnow() >= expires_at:
        logger.info("Zoho token expired, refreshing...")

        token_url = "https://accounts.zoho.in/oauth/v2/token"

        params = {
            "refresh_token": cred.refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
        }

        res = requests.post(token_url, params=params)
        res.raise_for_status()

        data = res.json()

        cred.access_token = data.get("access_token")
        cred.expires_in = data.get("expires_in")
        cred.updated_at = datetime.utcnow()

        db.commit()

        return cred.access_token

    return cred.access_token


ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc")

def is_resume(filename):
    return filename.lower().endswith(ALLOWED_EXTENSIONS)


def save_attachment_bytes(file_bytes, filename):
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    base, ext = os.path.splitext(filename)
    unique_name = filename
    counter = 0

    while os.path.exists(os.path.join(ATTACHMENT_DIR, unique_name)):
        counter += 1
        unique_name = f"{base}_{counter}{ext}"

    path = os.path.join(ATTACHMENT_DIR, unique_name)

    with open(path, "wb") as f:
        f.write(file_bytes)

    return unique_name, path

def get_account_id(headers):
    res = requests.get(f"{BASE_URL}/accounts", headers=headers)
    res.raise_for_status()
    return res.json()["data"][0]["accountId"]


def get_folders(account_id, headers):
    res = requests.get(f"{BASE_URL}/accounts/{account_id}/folders", headers=headers)
    res.raise_for_status()
    return res.json().get("data", [])


def get_messages(account_id, folder_id, headers):
    url = f"{BASE_URL}/accounts/{account_id}/messages/view"

    params = {
        "folderId": folder_id,
        "limit": 10
    }

    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()

    return res.json().get("data", [])


def get_attachments(account_id, folder_id, message_id, headers):
    url = f"{BASE_URL}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachmentinfo"

    res = requests.get(url, headers=headers)
    res.raise_for_status()

    data = res.json().get("data", {})
    return data.get("attachments", [])

def download_attachment(account_id, folder_id, message_id, attachment, headers):
    attachment_id = attachment["attachmentId"]
    filename = attachment["attachmentName"]

    url = f"{BASE_URL}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachments/{attachment_id}"

    res = requests.get(url, headers=headers)
    res.raise_for_status()

    return save_attachment_bytes(res.content, filename)

def fetch_emails_zoho(email_id: str) -> dict:
    db = SessionLocal()

    try:
        access_token = get_valid_zoho_token(email_id, db)

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        account_id = get_account_id(headers)
        folders = get_folders(account_id, headers)

        inbox_id = None
        for f in folders:
            if f["folderName"].lower() == "inbox":
                inbox_id = f["folderId"]
                break

        if not inbox_id:
            raise Exception("Inbox not found")
        messages = get_messages(account_id, inbox_id, headers)

        processed_count = 0

        for msg in messages:
            message_id = msg.get("messageId")
            existing = db.query(EmailLogs).filter(
                EmailLogs.message_id == message_id
            ).first()

            if existing:
                continue

            subject = msg.get("subject", "")
            sender = msg.get("fromAddress", "")
            email_obj = EmailLogs(
                message_id=message_id,
                subject=subject,
                sender=sender,
            )
            db.add(email_obj)
            db.commit()
            db.refresh(email_obj)
            attachments = get_attachments(account_id, inbox_id, message_id, headers)

            for att in attachments:
                filename = att["attachmentName"]
                if not is_resume(filename):
                    logger.info(f"Skipping: {filename}")
                    continue

                filename, path = download_attachment(
                    account_id,
                    inbox_id,
                    message_id,
                    att,
                    headers
                )

                attachment = Attachment(
                    email_id=email_obj.email_id,
                    file_name=filename,
                )
                db.add(attachment)
                db.commit()
            celery_task = resume_track.delay(str(email_obj.email_id))

            logger.info(f"Processed Zoho email: {subject}, task: {celery_task.id}")

            processed_count += 1

        return {
            "status": "success",
            "message": "Zoho emails processed",
            "processed_count": processed_count
        }

    except Exception as e:
        logger.error(f"Error in fetch_emails_zoho: {str(e)}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()