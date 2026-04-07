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
from src.services.auth.gmail.service import gmail_login
from src.services.auth.gmail.service import gmail_callback

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(
	tags=["Payment-Process"],
	responses={
		400: {"description": "Bad Request"},
		404: {"description": "Not Found"},
		500: {"description": "Internal Server Error"},
	},
)

AUTH_URL = os.getenv("AUTH_URL")
TOKEN_URL = os.getenv("TOKEN_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

@router.get("oauth/login/gmail")
def oauth_gmail_login():
    """Initiate OAuth flow by redirecting user to Google's auth page."""
    response = gmail_login()
    return response

@router.get("/auth/callback")
def callback(code: str):
    """Handle OAuth callback and exchange code for tokens."""

    response = gmail_callback(code)
    return response
    

access_token = "a29.a0Aa7MYiptV9vzd0Cfkvcv6oStYEz_8KpCwoc_0_7ZlTsH1kFvQqaR4z4UegENvd-KvpmcCbFXb648seAbaLAmmOg0omrby7EpceZO182QeNamIOsVtAKPxKWKWuZf2q4f_SQwLR2W3HTxZepz2HnDUJk8sD_uqJ0vXPi-wdXfd-JcbN7F4rjtWnjYgZssWorQ_D6oYiUaCgYKAU4SARISFQHGX2MicByFpU8bMz12pJqA24YswA0206"

# @router.get("/emails")
# def fetch_oauth_gmails() -> dict:
#     db = SessionLocal()

#     access_token = "ya29.a0Aa7MYiptV9vzd0Cfkvcv6oStYEz_8KpCwoc_0_7ZlTsH1kFvQqaR4z4UegENvd-KvpmcCbFXb648seAbaLAmmOg0omrby7EpceZO182QeNamIOsVtAKPxKWKWuZf2q4f_SQwLR2W3HTxZepz2HnDUJk8sD_uqJ0vXPi-wdXfd-JcbN7F4rjtWnjYgZssWorQ_D6oYiUaCgYKAU4SARISFQHGX2MicByFpU8bMz12pJqA24YswA0206"

#     headers = {
#         "Authorization": f"Bearer {access_token}"
#     }

#     params = {
#         "q": "is:unread",
#         "maxResults": 10
#     }

#     response = requests.get(GMAIL_LIST_URL, headers=headers)
#     data = response.json()
#     logger.info(f"NAV----> Gmail API response: {data}")

#     messages = data.get("messages", [])

#     if not messages:
#         return {"message": "No new emails"}

#     for msg in messages:
#         message_id = msg["id"]

#         existing = db.query(EmailLogs).filter(
#             EmailLogs.message_id == message_id
#         ).first()

#         if existing:
#             continue
        
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

#     return {
#         "subject": subject,
#         "sender": sender
#     }


# @router.get("/emails")
# def fetch_emails_oauth() -> dict:
#     response = fetch_gmails()
#     return response
    







#zoho testing#


@router.get("/auth/zoho/callback")
async def zoho_callback(request: Request):
    code = request.query_params.get("code")

    token_url = "https://accounts.zoho.in/oauth/v2/token"

    CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
    CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
    REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    response = requests.post(token_url, data=data)
    tokens = response.json()

    logger.info(f"NAV----> Zoho tokens: {tokens}")

    return {"message": "OAuth Success", "tokens": tokens}




ZOHO_ACCESS_TOKEN = "1000.69b68bb62cf8e94b220a2b4287326d4b.fc709f9f04960d3fc978eb57424d9b8d"
ZOHO_MAIL_BASE = "https://mail.zoho.in"


@router.get("/zoho/accounts")
def get_account_and_emails(limit: int = 10):
    headers = {
        "Authorization": f"Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}"
    }

    # ✅ STEP 1: Get Account ID
    accounts_url = f"{ZOHO_MAIL_BASE}/api/accounts"
    acc_response = requests.get(accounts_url, headers=headers)

    if acc_response.status_code != 200:
        raise HTTPException(
            status_code=acc_response.status_code,
            detail="Failed to fetch Zoho mail account"
        )

    acc_data = acc_response.json()

    if not acc_data.get("data"):
        raise HTTPException(status_code=404, detail="No Zoho mail account found")

    account = acc_data["data"][0]
    account_id = account["accountId"]

    # ✅ STEP 2: Fetch Emails using Account ID
    mails_url = f"{ZOHO_MAIL_BASE}/api/accounts/{account_id}/messages/view"
    mails_response = requests.get(
        mails_url,
        headers=headers,
        params={"limit": limit}
    )

    if mails_response.status_code != 200:
        raise HTTPException(
            status_code=mails_response.status_code,
            detail="Failed to fetch emails"
        )

    mails_data = mails_response.json()

    return {
        "account_id": account_id,
        "mailbox": account.get("mailboxAddress"),
        "emails": mails_data
    }

# @router.get("/zoho/accounts")
# def get_account_id():
#     zoho_access_token = "1000.69b68bb62cf8e94b220a2b4287326d4b.fc709f9f04960d3fc978eb57424d9b8d" 

#     url = "https://mail.zoho.in/api/accounts"
#     headers = {
#         "Authorization": f"Zoho-oauthtoken {zoho_access_token}"
#     }

#     response = requests.get(url, headers=headers)
    

#     try:
#         data = response.json()
#         return data
#     except Exception:
#         return {
#             "error": "Invalid response",
#             "status": response.status_code,
#             "content": response.text
#         }



# zoho_access_token = "1000.0bf34494f301e58e58d627e05896ad52.c489272f962fe98fa5f053593edd2000"

# def fetch_emails(access_token, account_id):
#     url = f"https://mail.zoho.com/api/accounts/{account_id}/messages/view"

#     headers = {
#         "Authorization": f"Zoho-oauthtoken {access_token}"
#     }

#     params = {
#         "limit": 10
#     }

#     response = requests.get(url, headers=headers, params=params)
#     return response.json()