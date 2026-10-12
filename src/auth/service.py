"""Auth module service layer.

Combines OAuth email synchronization, OAuth token revocation and logout services,
and external provider integrations into domain service classes.
"""

from contextlib import contextmanager
import logging
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError
import requests
from sqlalchemy.orm import Session

from db.connection import SessionLocal
from src.admin.models import Users
from src.auth.jwt import decode_access_token
from src.auth.models import OauthCredentials, OauthSource
from src.auth.schemas import EmailFetchResponse, EmailFetchResult
from src.integrations.google import google_service
from src.integrations.zoho import zoho_service

load_dotenv()
logger = logging.getLogger(__name__)


# =============================================================================
# 1. Base Service
# =============================================================================

class BaseService:
    """Base service offering transactional DB session management."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    @contextmanager
    def get_session(self, session: Optional[Session] = None) -> Generator[Session, None, None]:
        """Provide a transactional database session scope."""
        if session is not None:
            yield session
            return
        if self._db is not None:
            yield self._db
            return
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


# =============================================================================
# 2. OAuth Email Synchronization Service
# =============================================================================

class OAuthEmailService(BaseService):
    """Handles fetching emails for active authorized accounts via OAuth providers."""

    def fetch_emails_oauth(self, session: Optional[Session] = None) -> EmailFetchResponse:
        """Fetch emails from all active users based on OAuth source (Gmail / Zoho).

        Returns:
            EmailFetchResponse: Aggregated status and per-account fetch results.
        """
        logger.info("Fetching emails for all active users")
        with self.get_session(session) as db:
            results: List[EmailFetchResult] = []
            try:
                # 1. Get all active users
                users = db.query(Users).filter(
                    Users.is_blocked.is_(False),
                    Users.is_active.is_(True),
                ).all()
                logger.info("Found %d active email accounts", len(users))
                if not users:
                    return EmailFetchResponse(
                        message="No active email accounts found",
                        results=[],
                    )

                for mail in users:
                    email_id = (mail.email_address or "").strip()
                    if not email_id:
                        logger.warning("Empty email found, skipping...")
                        continue

                    logger.info("Processing email: %s", email_id)

                    # 2. Fetch OAuth credentials
                    cred = db.query(OauthCredentials).filter(
                        OauthCredentials.email == email_id,
                        OauthCredentials.is_active.is_(True),
                    ).first()

                    if not cred:
                        logger.warning("No OAuth credentials found for %s", email_id)
                        continue

                    if not cred.source:
                        logger.warning("No source mapped for %s", email_id)
                        continue

                    # 3. Identify source
                    source_name = cred.source.source_name.lower().strip()
                    logger.info("Source detected: %s", source_name)

                    # 4. Call respective service
                    service_response = None
                    fetch_status = "unknown"
                    try:
                        if source_name == "gmail":
                            service_response = google_service.fetch_emails_gmail(email_id=email_id)
                            fetch_status = "success"
                        elif source_name == "zoho":
                            service_response = zoho_service.fetch_emails_zoho(email_id=email_id)
                            fetch_status = "success"
                        else:
                            logger.warning("Unsupported source: %s", source_name)
                    except Exception as service_error:
                        logger.error("Error processing %s: %s", email_id, str(service_error))
                        fetch_status = f"failed: {str(service_error)}"

                    if service_response is None:
                        service_response = {"processed_count": 0}

                    results.append(
                        EmailFetchResult(
                            email=email_id,
                            source=source_name,
                            status=fetch_status,
                            processed_count=service_response.get("processed_count", 0),
                        )
                    )

                return EmailFetchResponse(
                    message="Email fetching completed",
                    results=results,
                )

            except Exception as e:
                logger.error("Fatal error in fetch_emails_oauth: %s", str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"status": "error", "message": str(e)},
                )

    def fetch_oauth_email_by_id(self, email_id: str, session: Optional[Session] = None) -> Dict[str, Any]:
        """Fetch emails for a specific email address via configured OAuth credentials."""
        logger.info("Fetching emails for specific email: %s", email_id)
        with self.get_session(session) as db:
            cred = None
            try:
                email_id = email_id.strip() if email_id else ""
                if not email_id:
                    return {
                        "status": "error",
                        "message": "Email address is required",
                        "source": None,
                        "processed_count": 0,
                    }

                # 1. Check if user exists in Users table
                user = db.query(Users).filter(
                    Users.email_address == email_id,
                    Users.is_blocked.is_(False),
                    Users.is_active.is_(True),
                ).first()

                if not user:
                    return {
                        "status": "error",
                        "message": f"User with email '{email_id}' not found or inactive/ blocked",
                        "source": None,
                        "processed_count": 0,
                    }

                # 2. Fetch OAuth credentials
                cred = db.query(OauthCredentials).filter(
                    OauthCredentials.email == email_id,
                    OauthCredentials.is_active.is_(True),
                ).first()

                if not cred:
                    return {
                        "status": "error",
                        "message": f"No OAuth credentials found for {email_id}. Please connect via OAuth first.",
                        "source": None,
                        "processed_count": 0,
                    }

                if not cred.source:
                    return {
                        "status": "error",
                        "message": f"No OAuth source mapped for {email_id}",
                        "source": None,
                        "processed_count": 0,
                    }

                # 3. Identify source
                source_name = cred.source.source_name.lower().strip()
                logger.info("Source detected: %s", source_name)

                # 4. Update sync_status to "syncing"
                cred.sync_status = "syncing"
                db.commit()

                # 5. Call respective service
                try:
                    if source_name == "gmail":
                        service_response = google_service.fetch_emails_gmail(email_id=email_id)
                    elif source_name == "zoho":
                        service_response = zoho_service.fetch_emails_zoho(email_id=email_id)
                    else:
                        cred.sync_status = "failed"
                        db.commit()
                        return {
                            "status": "error",
                            "message": f"Unsupported source: {source_name}. Supported: gmail, zoho",
                            "source": source_name,
                            "processed_count": 0,
                        }

                    # 6. Update sync_status to "completed" on success
                    cred.sync_status = "completed"
                    db.commit()

                    return {
                        "status": "success",
                        "message": service_response.get("message", "Emails fetched successfully"),
                        "source": source_name,
                        "processed_count": service_response.get("processed_count", 0),
                    }

                except Exception as service_error:
                    logger.error("Error processing %s: %s", email_id, str(service_error))
                    cred.sync_status = "failed"
                    db.commit()
                    return {
                        "status": "error",
                        "message": f"Failed to process emails: {str(service_error)}",
                        "source": source_name,
                        "processed_count": 0,
                    }

            except Exception as e:
                logger.error("Fatal error in fetch_oauth_email_by_id: %s", str(e))
                if cred:
                    cred.sync_status = "failed"
                    db.commit()
                return {
                    "status": "error",
                    "message": str(e),
                    "source": None,
                    "processed_count": 0,
                }


# =============================================================================
# 3. OAuth Token Revocation & Logout Service
# =============================================================================

class OAuthLogoutService(BaseService):
    """Handles token revocation and logout for OAuth accounts across providers."""

    def revoke_zoho_token(self, oauth_cred) -> bool:
        """Revoke Zoho access or refresh token with regional accounts server."""
        token_to_revoke = oauth_cred.refresh_token or oauth_cred.access_token
        if not token_to_revoke:
            logger.warning("Cannot revoke Zoho token: no token available for %s", oauth_cred.email)
            return False

        token_type = "refresh_token" if oauth_cred.refresh_token else "access_token"
        api_domain = oauth_cred.api_domain or ""

        if not api_domain and oauth_cred.email and "zohomail.in" in oauth_cred.email:
            api_domain = "https://www.zohoapis.in"
            logger.warning("api_domain was empty, inferred from email for %s", oauth_cred.email)

        logger.info(
            "Zoho revoke — email: %s, api_domain: '%s', token_type: %s",
            oauth_cred.email,
            api_domain,
            token_type,
        )

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
            revoke_url = "https://accounts.zoho.com/oauth/v2/token/revoke"
            logger.warning("api_domain '%s' fell back to global accounts.zoho.com", api_domain)

        try:
            logger.info("Revoking Zoho %s at %s for %s", token_type, revoke_url, oauth_cred.email)
            response = requests.post(
                revoke_url,
                params={"token": token_to_revoke},
                timeout=10,
            )
            logger.info("Zoho revoke status: %s", response.status_code)

            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    logger.info("Zoho revoke response JSON: %s", resp_json)
                    if resp_json.get("status") == "success":
                        logger.info("Zoho %s revoked successfully for %s", token_type, oauth_cred.email)
                        return True
                    else:
                        logger.warning("Zoho revoke unexpected response: %s", resp_json)
                        return False
                except Exception:
                    logger.info("Zoho revoke returned 200 with non-JSON body — treating as success")
                    return True
            else:
                logger.warning("Zoho revoke failed: %s — %s", response.status_code, response.text[:300])
                return False

        except requests.RequestException as e:
            logger.error("Request error revoking Zoho token for %s: %s", oauth_cred.email, e)
            return False
        except Exception as e:
            logger.error("Unexpected error revoking Zoho token for %s: %s", oauth_cred.email, e)
            return False

    def revoke_gmail_token(self, refresh_token: str) -> bool:
        """Revoke Gmail refresh token to invalidate OAuth session."""
        try:
            if not refresh_token:
                logger.warning("Cannot revoke Gmail token: refresh_token is empty")
                return False

            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": refresh_token},
                timeout=10,
            )

            if response.ok:
                logger.info("Gmail refresh token revoked successfully")
                return True
            else:
                logger.warning("Failed to revoke Gmail token: %s - %s", response.status_code, response.text)
                return False

        except Exception as e:
            logger.error("Error revoking Gmail token: %s", str(e))
            return False

    def logout_user(self, email: str, session: Optional[Session] = None) -> Dict[str, Any]:
        """Perform complete logout for a user across all OAuth providers.

        1. Finds the user's OAuth credentials
        2. Determines the provider (Gmail / Zoho)
        3. Revokes the token with the provider
        4. Updates DB session
        """
        with self.get_session(session) as db:
            try:
                oauth_cred = db.query(OauthCredentials).filter(
                    OauthCredentials.email == email
                ).first()

                if not oauth_cred:
                    logger.warning("No OAuth credentials found for %s", email)
                    return {
                        "status": "success",
                        "data": {
                            "email": email,
                            "providers_revoked": [],
                            "errors": [],
                        },
                    }

                api_domain = oauth_cred.api_domain or ""
                if not api_domain and ("zohomail" in email or "zoho" in email):
                    api_domain = "https://www.zohoapis.in"
                    logger.warning("api_domain missing for %s, inferred from email domain", email)

                errors: List[str] = []
                revoked: List[str] = []

                if "zoho" in api_domain.lower():
                    success = self.revoke_zoho_token(oauth_cred)
                    provider = "zoho"
                elif "google" in api_domain.lower():
                    success = self.revoke_gmail_token(oauth_cred.refresh_token)
                    provider = "gmail"
                else:
                    logger.warning("Unknown provider for api_domain: '%s' — skipping revocation", api_domain)
                    success = False
                    provider = "unknown"

                if success:
                    revoked.append(provider)
                else:
                    errors.append(f"Failed to revoke {provider} token")

                db.commit()
                logger.info("OAuth logout completed for %s", email)

                return {
                    "status": "success",
                    "data": {
                        "email": email,
                        "providers_revoked": revoked,
                        "errors": errors,
                    },
                }

            except Exception as e:
                db.rollback()
                logger.error("Error in logout_user for %s: %s", email, str(e))
                return {
                    "status": "error",
                    "message": f"Logout failed: {str(e)}",
                }

    def logout(self, auth_header: Optional[str]) -> Dict[str, Any]:
        """Validate Authorization header, decode token email, and trigger logout.

        Args:
            auth_header: Full 'Bearer <token>' Authorization header.

        Returns:
            Dict: Success response or raises appropriate HTTPException.
        """
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Missing or invalid Authorization header"},
            )

        token = auth_header.split(" ")[1]

        try:
            payload = decode_access_token(token)
            email = payload.get("email")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"status": "error", "message": "Token missing email claim"},
                )
        except JWTError as e:
            logger.error("Invalid token during logout: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Invalid or expired token"},
            )

        logger.info("Logout request for email: %s", email)
        result = self.logout_user(email)

        if result.get("status") == "success":
            return {
                "status": status.HTTP_200_OK,
                "message": "Logout successful",
                "data": result.get("data", {}),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": result.get("message", "Logout failed")},
            )


# =============================================================================
# 4. OAuth Provider Integrations Service
# =============================================================================

class OAuthIntegrationService(BaseService):
    """Encapsulates login URLs generation and callback exchanges for Google and Zoho."""

    def gmail_login(self) -> Dict[str, Any]:
        """Initiate Gmail OAuth login flow."""
        return google_service.gmail_login()

    def gmail_callback(self, code: str) -> Dict[str, Any]:
        """Exchange Gmail authorization code for access and refresh tokens."""
        return google_service.gmail_callback(code)

    def zoho_login(self) -> Dict[str, Any]:
        """Initiate Zoho OAuth login flow."""
        return zoho_service.zoho_login()

    def zoho_callback(self, code: str) -> Dict[str, Any]:
        """Exchange Zoho authorization code for access and refresh tokens."""
        return zoho_service.zoho_callback(code)


# =============================================================================
# 5. Unified Auth Service Facade
# =============================================================================

class AuthService(
    OAuthEmailService,
    OAuthLogoutService,
    OAuthIntegrationService,
):
    """Unified authentication service facade combining OAuth email sync, logout, and provider flows."""

    def __init__(self, db: Optional[Session] = None):
        super().__init__(db=db)


# Global singleton instance
auth_service = AuthService()


# =============================================================================
# 6. Backward-Compatible Function Exports
# =============================================================================

def fetch_emails_oauth() -> EmailFetchResponse:
    return auth_service.fetch_emails_oauth()

def fetch_oauth_email_by_id(email_id: str) -> Dict[str, Any]:
    return auth_service.fetch_oauth_email_by_id(email_id)

def revoke_zoho_token(oauth_cred) -> bool:
    return auth_service.revoke_zoho_token(oauth_cred)

def revoke_gmail_token(refresh_token: str) -> bool:
    return auth_service.revoke_gmail_token(refresh_token)

def logout_user(email: str) -> Dict[str, Any]:
    return auth_service.logout_user(email)

def logout(auth_header: Optional[str]) -> Dict[str, Any]:
    return auth_service.logout(auth_header)

def gmail_login_service() -> Dict[str, Any]:
    return auth_service.gmail_login()

def gmail_callback_service(code: str) -> Dict[str, Any]:
    return auth_service.gmail_callback(code)

def zoho_login_service() -> Dict[str, Any]:
    return auth_service.zoho_login()

def zoho_callback_service(code: str) -> Dict[str, Any]:
    return auth_service.zoho_callback(code)


__all__ = [
    "BaseService",
    "OAuthEmailService",
    "OAuthLogoutService",
    "OAuthIntegrationService",
    "AuthService",
    "auth_service",
    "fetch_emails_oauth",
    "fetch_oauth_email_by_id",
    "revoke_zoho_token",
    "revoke_gmail_token",
    "logout_user",
    "logout",
    "gmail_login_service",
    "gmail_callback_service",
    "zoho_login_service",
    "zoho_callback_service",
]