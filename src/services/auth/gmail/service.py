from fastapi.responses import RedirectResponse
from fastapi import Request
import requests
import logging
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
import os
from urllib.parse import urlencode
from db.connection import SessionLocal
from src.email_reader.models import EmailLogs
# from src.services.auth.gmail.service import gmail_login

load_dotenv()
logger = logging.getLogger(__name__)

AUTH_URL = os.getenv("AUTH_URL")
TOKEN_URL = os.getenv("TOKEN_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")


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
        raise HTTPException(status_code=500, detail="Error generating auth URL")
    
def gmail_callback(code: str) -> Dict[str, Any]:    
    logger.info(f"NAV----> Received auth code: {code}")

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        response = requests.post(TOKEN_URL, data=data)
        tokens = response.json()
        # TODO: Implement token storage logic
        return {
            "status": "success",
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
        }
    except Exception as e:
        logger.error(f"Error fetching tokens: {e}")
        raise HTTPException(status_code=500, detail="Error fetching tokens")
    

# def process_parts(payload, message_id, email_obj, access_token, db):
#     parts = payload.get("parts", [])

#     for part in parts:
#         filename = part.get("filename")

#         if filename:
#             body = part.get("body", {})
#             attachment_id = body.get("attachmentId")

#             if attachment_id:
#                 att_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}"

#                 headers = {
#                     "Authorization": f"Bearer {access_token}"
#                 }

#                 att_res = requests.get(att_url, headers=headers)
#                 att_data = att_res.json()

#                 file_data = att_data.get("data")

#                 import base64
#                 decoded = base64.urlsafe_b64decode(file_data)

#                 path = f"attachments/{filename}"
#                 with open(path, "wb") as f:
#                     f.write(decoded)

#                 text = extract_attachment_text(path)

#                 if not text.strip():
#                     continue

#                 resume_flag = is_resume(text)

#                 attachment = Attachment(
#                     email_id=email_obj.email_id,
#                     file_name=filename,
#                     is_resume=resume_flag
#                 )
#                 db.add(attachment)
#                 db.commit()
    
# def fetch_gmails() -> Dict[str, Any]:
#     #Need to get token from db
#     access_token = "ya29.a0Aa7MYiptV9vzd0Cfkvcv6oStYEz_8KpCwoc_0_7ZlTsH1kFvQqaR4z4UegENvd-KvpmcCbFXb648seAbaLAmmOg0omrby7EpceZO182QeNamIOsVtAKPxKWKWuZf2q4f_SQwLR2W3HTxZepz2HnDUJk8sD_uqJ0vXPi-wdXfd-JcbN7F4rjtWnjYgZssWorQ_D6oYiUaCgYKAU4SARISFQHGX2MicByFpU8bMz12pJqA24YswA0206"

#     GMAIL_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

#     db = SessionLocal()

#     headers = {
#         "Authorization": f"Bearer {access_token}"
#     }

#     # ✅ Step 1: Fetch unread emails (like new emails)
#     params = {
#         "q": "is:unread has:attachment",
#         "maxResults": 10
#     }

#     response = requests.get(GMAIL_LIST_URL, headers=headers, params=params)
#     data = response.json()

#     messages = data.get("messages", [])

#     if not messages:
#         return {"message": "No new emails"}

#     for msg in messages:
#         message_id = msg["id"]

#         # ✅ Step 2: Avoid duplicates (like UID check)
#         existing = db.query(EmailLogs).filter(
#             EmailLogs.message_id == message_id
#         ).first()

#         if existing:
#             continue

#         # ✅ Step 3: Get full email
#         msg_url = f"{GMAIL_LIST_URL}/{message_id}"
#         msg_res = requests.get(msg_url, headers=headers)
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

#         # ✅ Save email
#         email_obj = EmailLogs(
#             message_id=message_id,
#             subject=subject,
#             sender=sender
#         )
#         db.add(email_obj)
#         db.commit()
#         db.refresh(email_obj)

#         # ✅ Step 4: Handle attachments
#         # process_parts(payload, message_id, email_obj, access_token, db)

#         # ✅ Step 5: Mark as READ (VERY IMPORTANT)
#         # mark_as_read(message_id, access_token)

#         # ✅ Step 6: Trigger Celery
#         # resume_track.delay(str(email_obj.email_id))

#     return {"message": "Emails processed"}