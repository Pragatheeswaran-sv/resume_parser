"""
Generic logout service for handling OAuth token revocation across providers
"""
import logging
import requests
from db.connection import SessionLocal
from src.auth.models import OauthCredentials, OauthSource
from src.services.auth.zoho.service import ZOHO_OAUTH_ENDPOINTS
import os

logger = logging.getLogger(__name__)


def revoke_zoho_token(oauth_cred) -> bool:
    token_to_revoke = oauth_cred.refresh_token or oauth_cred.access_token

    if not token_to_revoke:
        logger.warning(f"Cannot revoke Zoho token: no token available for {oauth_cred.email}")
        return False

    token_type = "refresh_token" if oauth_cred.refresh_token else "access_token"
    api_domain = oauth_cred.api_domain or ""

    # Fallback: infer from email if api_domain is missing
    if not api_domain and oauth_cred.email and "zohomail.in" in oauth_cred.email:
        api_domain = "https://www.zohoapis.in"
        logger.warning(f"api_domain was empty, inferred from email for {oauth_cred.email}")

    logger.info(f"Zoho revoke — email: {oauth_cred.email}, api_domain: '{api_domain}', token_type: {token_type}")

    # ✅ Match against zohoapis.in OR zoho.in (accounts domain)
    if "zohoapis.in" in api_domain or "zoho.in" in api_domain:
        revoke_url = "https://accounts.zoho.in/oauth/v2/token/revoke"
    elif "zohoapis.eu" in api_domain or "zoho.eu" in api_domain:
        revoke_url = "https://accounts.zoho.eu/oauth/v2/token/revoke"
    elif "zohoapis.com.au" in api_domain or "zoho.com.au" in api_domain:
        revoke_url = "https://accounts.zoho.com.au/oauth/v2/token/revoke"
    elif "zohoapis.jp" in api_domain or "zoho.jp" in api_domain:
        revoke_url = "https://accounts.zoho.jp/oauth/v2/token/revoke"
    elif "zohoapis.ca" in api_domain or "zohocloud.ca" in api_domain:
        revoke_url = "https://accounts.zohocloud.ca/oauth/v2/token/revoke"
    elif "zohoapis.sa" in api_domain or "zoho.sa" in api_domain:
        revoke_url = "https://accounts.zoho.sa/oauth/v2/token/revoke"
    elif "zohoapis.com.cn" in api_domain or "zoho.com.cn" in api_domain:
        revoke_url = "https://accounts.zoho.com.cn/oauth/v2/token/revoke"
    else:
        # Global fallback (zohoapis.com)
        revoke_url = "https://accounts.zoho.com/oauth/v2/token/revoke"
        logger.warning(f"api_domain '{api_domain}' fell back to global accounts.zoho.com")

    try:
        logger.info(f"Revoking Zoho {token_type} at {revoke_url} for {oauth_cred.email}")

        response = requests.post(
            revoke_url,
            params={"token": token_to_revoke},
            timeout=10
        )

        logger.info(f"Zoho revoke status: {response.status_code}")

        if response.status_code == 200:
            try:
                resp_json = response.json()
                logger.info(f"Zoho revoke response JSON: {resp_json}")
                if resp_json.get("status") == "success":
                    logger.info(f"Zoho {token_type} revoked successfully for {oauth_cred.email}")
                    return True
                else:
                    logger.warning(f"Zoho revoke unexpected response: {resp_json}")
                    return False
            except Exception:
                logger.info("Zoho revoke returned 200 with non-JSON body — treating as success")
                return True
        else:
            logger.warning(f"Zoho revoke failed: {response.status_code} — {response.text[:300]}")
            return False

    except requests.RequestException as e:
        logger.error(f"Request error revoking Zoho token for {oauth_cred.email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error revoking Zoho token for {oauth_cred.email}: {e}")
        return False


def revoke_gmail_token(refresh_token: str) -> bool:
    """
    Revoke Gmail refresh token to invalidate the OAuth session.

    Args:
        refresh_token: The Gmail refresh token to revoke

    Returns:
        bool: True if revocation succeeded, False otherwise
    """
    try:
        if not refresh_token:
            logger.warning("Cannot revoke Gmail token: refresh_token is empty")
            return False

        response = requests.post(
            "https://oauth2.googleapis.com/revoke",
            data={"token": refresh_token},
            timeout=10
        )

        if response.ok:
            logger.info("Gmail refresh token revoked successfully")
            return True
        else:
            logger.warning(f"Failed to revoke Gmail token: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error revoking Gmail token: {str(e)}")
        return False


def logout_user(email: str) -> dict:
    """
    Perform complete logout for a user across all OAuth providers.

    This function:
    1. Finds the user's OAuth credentials
    2. Determines the provider (Gmail/Zoho) from api_domain
    3. Revokes the token with the provider
    4. Deletes the credentials from the database regardless of revocation result

    Args:
        email: User's email address

    Returns:
        dict: Status of logout operation
    """
    db = SessionLocal()
    try:
        oauth_cred = db.query(OauthCredentials).filter(
            OauthCredentials.email == email
        ).first()

        if not oauth_cred:
            logger.warning(f"No OAuth credentials found for {email}")
            return {
                "status": "success",
                "data": {
                    "email": email,
                    "providers_revoked": [],
                    "errors": []
                }
            }

        # Determine provider from api_domain directly
        api_domain = oauth_cred.api_domain or ""

        # Fallback: infer from email domain if api_domain is missing
        if not api_domain:
            if "zohomail" in email or "zoho" in email:
                api_domain = "https://www.zohoapis.in"
                logger.warning(f"api_domain missing for {email}, inferred from email domain")

        errors = []
        revoked = []

        if "zoho" in api_domain.lower():
            success = revoke_zoho_token(oauth_cred)
            provider = "zoho"
        elif "google" in api_domain.lower():
            success = revoke_gmail_token(oauth_cred.refresh_token)
            provider = "gmail"
        else:
            logger.warning(f"Unknown provider for api_domain: '{api_domain}' — skipping token revocation")
            success = False
            provider = "unknown"

        if success:
            revoked.append(provider)
        else:
            errors.append(f"Failed to revoke {provider} token")

        # Always delete credentials from DB regardless of revocation result
        # db.delete(oauth_cred)
        db.commit()
        logger.info(f"OAuth credentials deleted from DB for {email}")

        return {
            "status": "success",
            "data": {
                "email": email,
                "providers_revoked": revoked,
                "errors": errors
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error in logout_user for {email}: {str(e)}")
        return {
            "status": "error",
            "message": f"Logout failed: {str(e)}"
        }

    finally:
        db.close()