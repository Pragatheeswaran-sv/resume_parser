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
import base64
from src.auth.jwt import create_access_token
from email.utils import parseaddr
from src.admin.models import Users

load_dotenv()
logger = logging.getLogger(__name__)

AUTH_URL = os.getenv("GMAIL_AUTH_URL")
TOKEN_URL = os.getenv("GMAIL_TOKEN_URL")
CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI")


def gmail_login()-> Dict[str, Any]:
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
        logger.info(f"NAV----> the url is: {url}")
        # return RedirectResponse(url)
        return {
            "status": "success",
            "auth_url": url
        }
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "error", "message": "Error generating auth URL"})
    
# def gmail_callback(code: str) -> Dict[str, Any]:    
#     logger.info(f"NAV----> Received auth code: {code}")

#     data = {
#         "code": code,
#         "client_id": CLIENT_ID,
#         "client_secret": CLIENT_SECRET,
#         "redirect_uri": REDIRECT_URI,
#         "grant_type": "authorization_code",
#     }
#     try:
#         response = requests.post(TOKEN_URL, data=data)
#         tokens = response.json()
#         # TODO: Implement token storage logic
#         return {
#             "status": "success",
#             "access_token": tokens.get("access_token"),
#             "refresh_token": tokens.get("refresh_token"),
#             "expires_in": tokens.get("expires_in"),
#         }
#     except Exception as e:
#         logger.error(f"Error fetching tokens: {e}")
#         raise HTTPException(status_code=500, detail="Error fetching tokens")

def gmail_callback(code: str, db = SessionLocal()) -> dict:
    

    try:
        logger.info(f"NAV----> Received auth code {code}")

        # 🔹 Step 1: Exchange code for tokens
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to get access token")

        # 🔹 Step 2: Get user email
        # userinfo_res = requests.get(
        #     "https://www.googleapis.com/oauth2/v2/userinfo",
        #     headers={"Authorization": f"Bearer {access_token}"}
        # )
        # userinfo_res.raise_for_status()

        # user_info = userinfo_res.json()
        # email = user_info.get("email")
        profile_res = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        profile_res.raise_for_status()

        profile_data = profile_res.json()
        email = profile_data.get("emailAddress")

        if not email:
            logger.error(f"User info response invalid: {profile_data}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "400", "message": "Unable to fetch user email"})

        logger.info(f"OAuth login success for email: {email}")

        # 🔹 Step 3: Validate Users
        # users = db.query(Users).filter(
        #     Users.email_address == email,
        #     Users.is_active == True
        # ).first()

        # if not users:
        #     logger.warning(f"Unauthorized email attempted: {email}")
        #     raise HTTPException(status_code=403, detail="Authentication failed")

        # 🔹 Step 4: Get or Create Gmail Source
        source = db.query(OauthSource).filter(
            OauthSource.source_name == "gmail"
        ).first()

        if not source:
            logger.info("Creating new Gmail source entry")
            source = OauthSource(
                source_name="gmail",
                created_by=email
            )
            db.add(source)
            db.commit()
            db.refresh(source)
        existing_cred = db.query(OauthCredentials).filter(
            OauthCredentials.email == email,
            OauthCredentials.source_id == source.source_id
        ).first()

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
                created_by=email
            )
            db.add(new_cred)

        db.commit()
        logger.info(f"NAV----> Credentials stored for {email}, expires at {expires_at.isoformat()}")
        
        logger.info(f"NAV----> Access token created for {email}")
        valid_mail = db.query(Users).filter(
            Users.email_address == email,
            Users.is_blocked == False,
            Users.is_active == True
        ).first()
        access_token = create_access_token({"email": email, "sub": str(valid_mail.user_id), "role": "user"})
        if not valid_mail:
            logger.warning(f"Email {email} is not authorized to connect")
            raise HTTPException(status_code=status.HTTP_200_OK, detail={"status": status.HTTP_401_UNAUTHORIZED, "message": "Email not authorized"})

        return {
            "status": status.HTTP_200_OK,
            "message": "OAuth connected successfully",
            "data":
                {
                    "name": valid_mail.name,
                    "email": email,
                    "access_token": access_token,
                    "is_admin": False,
                }
        }

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error during OAuth: {str(http_err)}")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "error", "message": "OAuth provider error"})

    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error: {str(req_err)}")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Network error during OAuth"})

    # except Exception as db_err:
    #     logger.error(f"Database error: {str(db_err)}")
    #     db.rollback()
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Database error"})

    except HTTPException:
        db.rollback()
        raise  # re-raise known errors

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Internal server error"})

    finally:
        db.close()
    

def get_valid_access_token(email: str, db = SessionLocal()):
    logger.info(f"NAV----> Fetching access token for {email}")
    email = email.strip()
    cred = db.query(OauthCredentials).filter(
        OauthCredentials.email == email
        # OauthCredentials.is_active == True
    ).first()

    if not cred:
        logger.error(f"No credentials found for {email}")
        raise Exception("OAuth credentials not found")
    expires_at = cred.updated_at + timedelta(seconds=cred.expires_in)

    if datetime.utcnow() >= expires_at:
        logger.info(f"NAV---->Access token expired for {email}, refreshing...")
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
 
def save_attachment_bytes(file_bytes, filename):
    logger.info(f"NAV----> Saving attachment")
    logger.info(f"NAV----> Saving attachment: {filename}")
    ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")

    if not os.path.exists(ATTACHMENT_DIR):
        os.makedirs(ATTACHMENT_DIR)

    base_name, ext = os.path.splitext(filename)
    unique_name = filename
    counter = 0
    while os.path.exists(os.path.join(ATTACHMENT_DIR, unique_name)):
        counter += 1
        unique_name = f"{base_name}_{counter}{ext}"

    path = os.path.join(ATTACHMENT_DIR, unique_name)
    with open(path, "wb") as f:
        f.write(file_bytes)

    return unique_name, path

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

def process_parts(payload, message_id, email_obj, access_token, db: SessionLocal()):
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
        filename, path = save_attachment_bytes(file_bytes, filename)

        attachment = Attachment(
            email_id=email_obj.email_id,
            file_name=filename,
        )
        db.add(attachment)
        db.commit()


def fetch_emails_gmail(email_id: str) -> dict:
    db = SessionLocal()
    gmail_list_url = os.getenv("GMAIL_LIST_URL", "https://gmail.googleapis.com/gmail/v1/users/me/messages")
    try:
        # 1. Get credentials and last sync time
        cred = db.query(OauthCredentials).filter(
            OauthCredentials.email == email_id.strip()
        ).first()

        if not cred:
            logger.error(f"No credentials found for {email_id}")
            return {"status": "error", "message": "Credentials not found"}

        access_token = get_valid_access_token(email_id, db)
        headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Build the query (Logic for last_processed_at)
        # Gmail 'after' search uses Unix timestamps
        query = "has:attachment"
        if cred.last_processed_at:
            # We add a 1-second buffer to avoid missing emails arriving exactly at the same time
            ts = int(cred.last_processed_at.timestamp())
            query += f" after:{ts}"
        
        logger.info(f"NAV----> Gmail Query: {query}")
        params = {
            "q": query
        }

        resp = requests.get(gmail_list_url, headers=headers, params=params)
        resp.raise_for_status()

        data = resp.json()
        messages = data.get("messages", [])
        if not messages:
            # Even if no messages, update the sync time to now
            cred.last_processed_at = datetime.utcnow()
            db.commit()
            return {"status": "success", "message": "No new emails found"}

        processed_count = 0
        for msg in messages:
            message_id = msg["id"]
            existing = db.query(EmailLogs).filter(
                EmailLogs.message_id == message_id
            ).first()

            if existing:
                continue
            msg_res = requests.get(
                f"{gmail_list_url}/{message_id}",
                headers=headers
            )
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
                    # sender = h["value"]
                    sender = parseaddr(h["value"])[1] 

            email_obj = EmailLogs(
                message_id=message_id,
                subject=subject,
                sender=sender,
                source_mail = email_id
            )
            db.add(email_obj)
            db.commit()
            db.refresh(email_obj)
            
            process_parts(payload, message_id, email_obj, access_token, db)

            # 🔹 Mark as read
            # requests.post(
            #     f"{gmail_list_url}/{message_id}/modify",
            #     headers=headers,
            #     json={"removeLabelIds": ["UNREAD"]},
            # )

            celery_task = resume_track.delay(str(email_obj.email_id))

            logger.info(f"Processed email: {subject}, task id: {celery_task.id}")

            processed_count += 1

        # 4. Update the sync timestamp to current time after successful batch
        cred.last_processed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Total emails processed for {email_id}: {processed_count}")
        return {
            "status": "success",
            "message": f"Gmail emails processed: {processed_count}",
            "processed_count": processed_count
        }

    except Exception as e:
        logger.error(f"Error in fetch_emails_gmail: {str(e)}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()

# def fetch_emails_gmail(gmail: str, db = SessionLocal()) -> dict:
#     """
#     Fetch new Gmail messages using OAuth and process attachments like your IMAP flow.
#     """

#     # Fetch unread emails with attachments (like your "new_uids")
#     params = {
#         "q": "is:unread has:attachment"
#     }
#     headers = {"Authorization": f"Bearer {access_token}"}

#     resp = requests.get(GMAIL_LIST_URL, headers=headers, params=params)
#     data = resp.json()
#     messages = data.get("messages", [])

#     if not messages:
#         return {"message": "No new emails"}

#     for msg in messages:
#         message_id = msg["id"]

#         # Skip if already in DB (like IMAP UID check)
#         existing = db.query(EmailLogs).filter(EmailLogs.message_id == message_id).first()
#         if existing:
#             continue

#         # Fetch full email
#         msg_res = requests.get(f"{GMAIL_LIST_URL}/{message_id}", headers=headers)
#         msg_data = msg_res.json()
#         payload = msg_data.get("payload", {})
#         headers_list = payload.get("headers", [])

#         subject = ""
#         sender = ""
#         for h in headers_list:
#             if h["name"] == "Subject":
#                 subject = h["value"]
#             if h["name"] == "From":
#                 sender = h["value"]

#         email_obj = EmailLogs(
#             message_id=message_id,
#             subject=subject,
#             sender=sender,
#         )
#         db.add(email_obj)
#         db.commit()
#         db.refresh(email_obj)

#         # Process attachments (like your IMAP save_attachment + DB)
#         process_parts(payload, message_id, email_obj, access_token, db)

#         # Mark as read (avoids fetching again next run)
#         requests.post(
#             f"{GMAIL_LIST_URL}/{message_id}/modify",
#             headers=headers,
#             json={"removeLabelIds": ["UNREAD"]},
#         )

#         # Trigger Celery task
#         celery_task = resume_track.delay(str(email_obj.email_id))
#         logger.info(f"Processed email {subject}, Celery task {celery_task.id}")

#     return {"message": "Emails processed", "processed_count": len(messages)}

# def zoho_callback(code: str, db=SessionLocal()) -> dict:
    # try:
    #     logger.info("Received Zoho auth code")
    #     token_url = "https://accounts.zoho.in/oauth/v2/token"

    #     token_data = {
    #         "code": code,
    #         "client_id": os.getenv("ZOHO_CLIENT_ID"),
    #         "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
    #         "redirect_uri": os.getenv("ZOHO_REDIRECT_URI"),
    #         "grant_type": "authorization_code",
    #     }

    #     token_res = requests.post(token_url, data=token_data)
    #     token_res.raise_for_status()

    #     tokens = token_res.json()

    #     access_token = tokens.get("access_token")
    #     refresh_token = tokens.get("refresh_token")
    #     scope = tokens.get("scope")
    #     logger.info(f"NAV----> Zoho access token: {access_token}")
    #     logger.info(f"NAV----> refresh token: {refresh_token}")
    #     logger.info(f"NAV----> scope: {scope}")
    #     expires_in = tokens.get("expires_in")

    #     if not access_token:
    #         logger.error(f"Zoho token response invalid: {tokens}")
    #         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "error", "message": "Failed to get access token"})

    #     # 🔹 Step 2: Get user email
    #     # userinfo_res = requests.get(
    #     #     "https://accounts.zoho.in/oauth/user/info",
    #     #     headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
    #     # )
    #     # userinfo_res.raise_for_status()

    #     # user_info = userinfo_res.json()
    #     # email = user_info.get("Email")
    #     accounts_res = requests.get(
    #         "https://mail.zoho.in/api/accounts",
    #         headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
    #     )
    #     accounts_res.raise_for_status()

    #     accounts_data = accounts_res.json()

    #     email = accounts_data["data"][0]["mailboxAddress"]

    #     if not email:
    #         logger.error(f"Zoho user info invalid: {accounts_data}")
    #         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "error", "message": "Unable to fetch user email"})

    #     logger.info(f"Zoho OAuth success for email: {email}")
    #     source = db.query(OauthSource).filter(
    #         OauthSource.source_name == "zoho"
    #     ).first()

    #     if not source:
    #         logger.info("Creating new Zoho source entry")
    #         source = OauthSource(
    #             source_name="zoho",
    #             created_by=email
    #         )
    #         db.add(source)
    #         db.commit()
    #         db.refresh(source)

    #     existing_cred = db.query(OauthCredentials).filter(
    #         OauthCredentials.email == email,
    #         OauthCredentials.source_id == source.source_id
    #     ).first()

    #     if existing_cred:
    #         logger.info(f"Updating Zoho credentials for {email}")

    #         existing_cred.access_token = access_token
    #         if refresh_token:
    #             existing_cred.refresh_token = refresh_token

    #         existing_cred.expires_in = expires_in
    #         existing_cred.updated_by = email

    #     else:
    #         logger.info(f"Creating new Zoho credentials for {email}")

    #         new_cred = OauthCredentials(
    #             email=email,
    #             access_token=access_token,
    #             refresh_token=refresh_token,
    #             expires_in=expires_in,
    #             source_id=source.source_id,
    #             created_by=email
    #         )
    #         db.add(new_cred)

    #     db.commit()

    #     access_token = create_access_token({"mail": email})

    #     valid_mail = db.query(Users).filter(
    #         Users.is_blocked == False,
    #         Users.email_address == email,
    #         Users.is_active == True
    #     ).first()
    #     if not valid_mail:
    #         logger.warning(f"Email {email} is not authorized to connect")
    #         raise HTTPException(status_code=status.HTTP_200_OK, detail={"status": status.HTTP_401_UNAUTHORIZED, "message": "Email not authorized"})

    #     return {
    #         "status": status.HTTP_200_OK,
    #         "message": "OAuth connected successfully",
    #         "data":
    #             {
    #                 "email": email,
    #                 "access_token": access_token,
    #                 "is_admin": False,
    #             }
    #     }

    # except requests.exceptions.HTTPError as http_err:
    #     logger.error(f"Zoho HTTP error: {str(http_err)}")
    #     db.rollback()
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "error", "message": "Zoho OAuth provider error"})

    # except requests.exceptions.RequestException as req_err:
    #     logger.error(f"Zoho request error: {str(req_err)}")
    #     db.rollback()
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Network error during Zoho OAuth"})

    # except HTTPException:
    #     db.rollback()
    #     raise

    # except Exception as e:
    #     logger.error(f"Zoho unexpected error: {str(e)}", exc_info=True)
    #     db.rollback()
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": "Internal server error"})

    # finally:
    #     db.close()