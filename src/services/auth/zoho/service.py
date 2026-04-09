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
from urllib.parse import urlparse
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


# def zoho_login():
#     try:
#         url = f"{ZOHO_AUTH_URL}?scope=ZohoMail.messages.ALL,ZohoMail.accounts.READ,ZohoMail.folders.READ&client_id={CLIENT_ID}&response_type=code&access_type=offline&prompt=consent&redirect_uri={REDIRECT_URI}"

#         return {
#                 "status": "success",
#                 "auth_url": url
#             }
#     except Exception as e:
#         logger.error(f"Error generating Zoho auth URL: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Error generating Zoho auth URL"})
    
# def get_valid_zoho_token(email: str, db: SessionLocal()):
#     logger.info(f"Fetching Zoho token for {email}")

#     cred = db.query(OauthCredentials).filter(
#         OauthCredentials.email == email
#     ).first()

#     if not cred:
#         raise Exception("Zoho credentials not found")

#     expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

#     if datetime.utcnow() >= expires_at:
#         logger.info("Zoho token expired, refreshing...")

#         token_url = "https://accounts.zoho.in/oauth/v2/token"

#         params = {
#             "refresh_token": cred.refresh_token,
#             "client_id": CLIENT_ID,
#             "client_secret": CLIENT_SECRET,
#             "grant_type": "refresh_token",
#         }

#         res = requests.post(token_url, params=params)
#         res.raise_for_status()

#         data = res.json()

#         cred.access_token = data.get("access_token")
#         cred.expires_in = data.get("expires_in")
#         cred.updated_at = datetime.utcnow()

#         db.commit()

#         return cred.access_token

#     return cred.access_token


# ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc")

# def is_resume(filename):
#     return filename.lower().endswith(ALLOWED_EXTENSIONS)


# def save_attachment_bytes(file_bytes, filename):
#     os.makedirs(ATTACHMENT_DIR, exist_ok=True)

#     base, ext = os.path.splitext(filename)
#     unique_name = filename
#     counter = 0

#     while os.path.exists(os.path.join(ATTACHMENT_DIR, unique_name)):
#         counter += 1
#         unique_name = f"{base}_{counter}{ext}"

#     path = os.path.join(ATTACHMENT_DIR, unique_name)

#     with open(path, "wb") as f:
#         f.write(file_bytes)

#     return unique_name, path

# def get_account_id(headers):
#     res = requests.get(f"{BASE_URL}/accounts", headers=headers)
#     res.raise_for_status()
#     return res.json()["data"][0]["accountId"]


# def get_folders(account_id, headers):
#     res = requests.get(f"{BASE_URL}/accounts/{account_id}/folders", headers=headers)
#     res.raise_for_status()
#     return res.json().get("data", [])


# def get_messages(account_id, folder_id, headers):
#     url = f"{BASE_URL}/accounts/{account_id}/messages/view"

#     params = {
#         "folderId": folder_id,
#         "limit": 10
#     }

#     res = requests.get(url, headers=headers, params=params)
#     res.raise_for_status()

#     return res.json().get("data", [])


# def get_attachments(account_id, folder_id, message_id, headers):
#     url = f"{BASE_URL}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachmentinfo"

#     res = requests.get(url, headers=headers)
#     res.raise_for_status()

#     data = res.json().get("data", {})
#     return data.get("attachments", [])

# def download_attachment(account_id, folder_id, message_id, attachment, headers):
#     attachment_id = attachment["attachmentId"]
#     filename = attachment["attachmentName"]

#     url = f"{BASE_URL}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachments/{attachment_id}"

#     res = requests.get(url, headers=headers)
#     res.raise_for_status()

#     return save_attachment_bytes(res.content, filename)

# def fetch_emails_zoho(email_id: str) -> dict:
#     db = SessionLocal()

#     try:
#         access_token = get_valid_zoho_token(email_id, db)

#         headers = {
#             "Authorization": f"Zoho-oauthtoken {access_token}"
#         }
#         account_id = get_account_id(headers)
#         folders = get_folders(account_id, headers)

#         inbox_id = None
#         for f in folders:
#             if f["folderName"].lower() == "inbox":
#                 inbox_id = f["folderId"]
#                 break

#         if not inbox_id:
#             raise Exception("Inbox not found")
#         messages = get_messages(account_id, inbox_id, headers)

#         processed_count = 0

#         for msg in messages:
#             message_id = msg.get("messageId")
#             existing = db.query(EmailLogs).filter(
#                 EmailLogs.message_id == message_id
#             ).first()

#             if existing:
#                 continue

#             subject = msg.get("subject", "")
#             sender = msg.get("fromAddress", "")
#             email_obj = EmailLogs(
#                 message_id=message_id,
#                 subject=subject,
#                 sender=sender,
#             )
#             db.add(email_obj)
#             db.commit()
#             db.refresh(email_obj)
#             attachments = get_attachments(account_id, inbox_id, message_id, headers)

#             for att in attachments:
#                 filename = att["attachmentName"]
#                 if not is_resume(filename):
#                     logger.info(f"Skipping: {filename}")
#                     continue

#                 filename, path = download_attachment(
#                     account_id,
#                     inbox_id,
#                     message_id,
#                     att,
#                     headers
#                 )

#                 attachment = Attachment(
#                     email_id=email_obj.email_id,
#                     file_name=filename,
#                 )
#                 db.add(attachment)
#                 db.commit()
#             celery_task = resume_track.delay(str(email_obj.email_id))

#             logger.info(f"Processed Zoho email: {subject}, task: {celery_task.id}")

#             processed_count += 1

#         return {
#             "status": "success",
#             "message": "Zoho emails processed",
#             "processed_count": processed_count
#         }

#     except Exception as e:
#         logger.error(f"Error in fetch_emails_zoho: {str(e)}", exc_info=True)
#         db.rollback()
#         raise

#     finally:
#         db.close()


def zoho_login():
    try:
        ZOHO_AUTH_BASE = "https://accounts.zoho.com"
        auth_url = (
            f"{ZOHO_AUTH_BASE}/oauth/v2/auth"
            f"?scope=ZohoMail.messages.ALL,ZohoMail.accounts.READ,ZohoMail.folders.READ"
            f"&client_id={os.getenv('ZOHO_CLIENT_ID')}"
            f"&response_type=code"
            f"&access_type=offline"
            f"&prompt=consent"
            f"&redirect_uri={os.getenv('ZOHO_REDIRECT_URI')}"
        )

        return {
            "status": "success",
            "auth_url": auth_url
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)}
        )
    

def get_mail_base_url(api_domain: str):
    return api_domain.replace("www.zohoapis", "mail.zoho") + "/api"

def get_accounts_base_url(api_domain: str):
    return api_domain.replace("www.zohoapis", "accounts.zoho")


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


def process_oauth_zoho_token(token_data: Dict[str, str],db=SessionLocal(), timeout: int = 10):
    """
    Exchanges a Zoho OAuth authorization/refresh token for access credentials.

    Tries all known Zoho regional OAuth endpoints until a valid token
    response is received.

    Args:
        token_data (Dict[str, str]): OAuth token request payload.
        db (Session): SQLAlchemy database session (reserved for future use).
        timeout (int): HTTP request timeout in seconds.

    Returns:
        Optional[Dict]: Token response containing access_token and related metadata.

    Raises:
        requests.HTTPError: If all endpoints fail with HTTP errors.
    """

    for token_url in ZOHO_OAUTH_ENDPOINTS:
        try:
            logger.debug("Requesting Zoho OAuth token from %s", token_url)
            response = requests.post(
                token_url,
                data=token_data,
                timeout=timeout,
            )
            response.raise_for_status()
            tokens = response.json()

            if tokens.get("access_token") or tokens.get("api_domain"):
                logger.info(
                    "Zoho OAuth token retrieved successfully from %s",
                    token_url,
                )
                logger.debug("Zoho token response: %s", tokens)
                return tokens

        except requests.RequestException as exc:
            logger.warning(
                "Zoho OAuth request failed for %s: %s",
                token_url,
                exc,
            )
            continue

    logger.error("Failed to retrieve Zoho OAuth token from all regions")
    return None


def zoho_callback(code: str, db=SessionLocal()):
    try:
        logger.info(f"NAV----> Received Zoho callback with code: {code}")

        token_data = {
            "code": code,
            "client_id": os.getenv("ZOHO_CLIENT_ID"),
            "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
            "redirect_uri": os.getenv("ZOHO_REDIRECT_URI"),
            "grant_type": "authorization_code",
        }

        tokens = process_oauth_zoho_token(token_data, db)

        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        api_domain = tokens.get("api_domain")   # 🔑 IMPORTANT
        expires_in = tokens.get("expires_in")
        logger.info(f"NAV----> Zoho token response: {tokens}")
        logger.info(f"NAV----> zoho_api_domain: {api_domain}")

        if not access_token or not api_domain:
            raise Exception("Invalid Zoho token response")

        BASE_URL = get_mail_base_url(api_domain)

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }

        accounts_res = requests.get(f"{BASE_URL}/accounts", headers=headers)
        accounts_res.raise_for_status()

        accounts_data = accounts_res.json()
        email = accounts_data["data"][0]["mailboxAddress"]
        logger.info(f"NAV----> Zoho account email: {email}")

        existing_cred = db.query(OauthCredentials).filter(
            OauthCredentials.email == email
        ).first()

        if existing_cred:
            existing_cred.access_token = access_token
            existing_cred.refresh_token = refresh_token or existing_cred.refresh_token
            existing_cred.expires_in = expires_in
            # existing_cred.api_domain = api_domain
            existing_cred.updated_at = datetime.utcnow()

        else:  
            new_cred = OauthCredentials(
                email=email,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                # api_domain=api_domain,   # 🔑 STORE THIS
                created_by=email
            )
            db.add(new_cred)

        db.commit()

        return {
            "status": "success",
            "email": email,
            "message": "Zoho OAuth connected successfully"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": str(e)}
        )

    finally:
        db.close()

def get_zoho_accounts_token_url(api_domain: str) -> str:
    """
    mail.zoho.in → https://accounts.zoho.in/oauth/v2/token
    """
    parsed = urlparse(api_domain)
    domain = parsed.netloc.replace("mail.", "")
    return f"https://accounts.{domain}/oauth/v2/token"

def get_mail_api_base(api_domain: str) -> str:
    return api_domain.rstrip("/") + "/api"


def get_valid_zoho_token(email: str, db = SessionLocal()) -> str:
    logger.info(f"Fetching Zoho token for {email}")

    cred = db.query(OauthCredentials).filter(
        OauthCredentials.email == email
    ).first()

    if not cred:
        raise Exception("Zoho credentials not found")

    expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

    if datetime.utcnow() >= expires_at:
        logger.info("Zoho token expired, refreshing...")

        token_url = get_zoho_accounts_token_url(cred.api_domain)

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

ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc")
def is_resume(filename: str) -> bool:
    return filename.lower().endswith(ALLOWED_EXTENSIONS)


def save_attachment_bytes(file_bytes: bytes, filename: str):
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    base, ext = os.path.splitext(filename)
    unique_name = filename
    counter = 1

    while os.path.exists(os.path.join(ATTACHMENT_DIR, unique_name)):
        unique_name = f"{base}_{counter}{ext}"
        counter += 1

    path = os.path.join(ATTACHMENT_DIR, unique_name)

    with open(path, "wb") as f:
        f.write(file_bytes)

    return unique_name, path

def get_account_id(api_domain, headers):
    base = get_mail_api_base(api_domain)
    res = requests.get(f"{base}/accounts", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()["data"][0]["accountId"]



def get_folders(api_domain, account_id, headers):
    base = get_mail_api_base(api_domain)
    res = requests.get(
        f"{base}/accounts/{account_id}/folders",
        headers=headers,
        timeout=10
    )
    res.raise_for_status()
    return res.json().get("data", [])


def get_messages(api_domain, account_id, folder_id, headers):
    base = get_mail_api_base(api_domain)
    res = requests.get(
        f"{base}/accounts/{account_id}/messages/view",
        headers=headers,
        params={"folderId": folder_id, "limit": 10},
        timeout=10
    )
    res.raise_for_status()
    return res.json().get("data", [])


def get_attachments(api_domain, account_id, folder_id, message_id, headers):
    base = get_mail_api_base(api_domain)
    res = requests.get(
        f"{base}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachmentinfo",
        headers=headers,
        timeout=10
    )
    res.raise_for_status()
    return res.json().get("data", {}).get("attachments", [])


def download_attachment(api_domain, account_id, folder_id, message_id, attachment, headers):
    base = get_mail_api_base(api_domain)
    attachment_id = attachment["attachmentId"]
    filename = attachment["attachmentName"]

    res = requests.get(
        f"{base}/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/attachments/{attachment_id}",
        headers=headers,
        timeout=10
    )
    res.raise_for_status()

    return save_attachment_bytes(res.content, filename)


def fetch_emails_zoho(email_id: str) -> dict:
    db = SessionLocal()

    try:
        cred = db.query(OauthCredentials).filter(
            OauthCredentials.email == email_id
        ).first()

        if not cred:
            raise Exception("Zoho credentials not found")

        access_token = get_valid_zoho_token(email_id, db)

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }

        api_domain = cred.api_domain

        account_id = get_account_id(api_domain, headers)
        folders = get_folders(api_domain, account_id, headers)

        inbox_id = next(
            (f["folderId"] for f in folders if f["folderName"].lower() == "inbox"),
            None
        )

        if not inbox_id:
            raise Exception("Inbox not found")

        messages = get_messages(api_domain, account_id, inbox_id, headers)

        processed_count = 0

        for msg in messages:
            message_id = msg["messageId"]

            if db.query(EmailLogs).filter(
                EmailLogs.message_id == message_id
            ).first():
                continue

            email_log = EmailLogs(
                message_id=message_id,
                subject=msg.get("subject", ""),
                sender=msg.get("fromAddress", ""),
            )

            db.add(email_log)
            db.commit()
            db.refresh(email_log)

            attachments = get_attachments(
                api_domain,
                account_id,
                inbox_id,
                message_id,
                headers
            )

            for att in attachments:
                if not is_resume(att["attachmentName"]):
                    continue

                filename, path = download_attachment(
                    api_domain,
                    account_id,
                    inbox_id,
                    message_id,
                    att,
                    headers
                )

                db.add(Attachment(
                    email_id=email_log.email_id,
                    file_name=filename
                ))
                db.commit()

            celery_task = resume_track.delay(str(email_log.email_id))
            logger.info(f"Processed email {email_log.subject}, task={celery_task.id}")

            processed_count += 1

        return {
            "status": "success",
            "processed_count": processed_count
        }

    except Exception as e:
        db.rollback()
        logger.error("Zoho fetch error", exc_info=True)
        raise

    finally:
        db.close()

