"""Admin service layer.

Business logic for administrator accounts, authorized email management,
and global extraction configuration.  Every public function uses its own
database session and raises ``ValueError`` on validation failures so the
API layer can translate them into appropriate HTTP responses.
"""

from typing import Any, Dict, List, Optional
import logging

from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, AuthMail, ExtractionConfig, ist_now
from src.auth.jwt import create_access_token, hash_password, verify_password
from fastapi import status

load_dotenv()
logger = logging.getLogger(__name__)


def admin_check(email: str, password: str) -> Dict[str, Any]:
    """Authenticate an admin by email and password, returning a JWT on success.

    Args:
        email: Admin email address.
        password: Plain-text password to verify.

    Returns:
        Dict containing an access token and admin profile info.

    Raises:
        ValueError: If credentials are missing or invalid.
    """
    session = SessionLocal()
    try:
        if not email or not password:
            raise ValueError("Email and password must be provided")

        admin = session.query(Admin).filter_by(email_address=email).first()
        if not admin:
            raise ValueError("Invalid email or password")

        if not admin.password or not verify_password(password, admin.password):
            raise ValueError("Invalid email or password")

        token = create_access_token({
            "sub": str(admin.admin_id),
            "email": admin.email_address,
            "role": "admin",
        })

        return {
            "status": status.HTTP_200_OK,
            "message": "Admin logged in successfully",
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "role": "admin",
                "name": admin.name,
                "email": admin.email_address,
            },
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("[admin_check] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def sso_user_login(email: str) -> Dict[str, Any]:
    """Issue a JWT for an SSO-authenticated user after verifying they exist
    in ``auth_mail`` and are not blocked.

    Args:
        email: Verified email from the SSO provider.

    Returns:
        Dict containing an access token and user profile info.

    Raises:
        ValueError: If the email is empty, not approved, or the account is blocked.
    """
    session = SessionLocal()
    try:
        if not email:
            raise ValueError("Email must be provided")

        account = (
            session.query(AuthMail)
            .filter(
                AuthMail.email_address == email,
                AuthMail.is_active.is_(True),
                AuthMail.is_blocked.is_(False),
            )
            .first()
        )
        if not account:
            raise ValueError("Access denied: email not approved or account blocked")

        token = create_access_token({
            "sub": str(account.auth_mail_id),
            "email": account.email_address,
            "role": "user",
        })

        return {
            "status": status.HTTP_200_OK,
            "message": "User logged in successfully",
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "role": "user",
                "email": account.email_address,
            },
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("[sso_user_login] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def new_admin(payload: dict) -> Dict[str, Any]:
    """Create a new administrator account.

    Args:
        payload: Dictionary with ``email``, ``password``, and optional ``name``.

    Returns:
        Dict with the newly created admin's ID and name.

    Raises:
        ValueError: If required fields are missing or the email is already taken.
    """
    session = SessionLocal()
    try:
        email = payload.get("email")
        password = payload.get("password")
        name = payload.get("name")

        if not email or not password:
            raise ValueError("Email and password are required")

        admin = session.query(Admin).filter_by(email_address=email).first()
        if admin:
            raise ValueError("Admin with this email already exists")

        new_admin_obj = Admin(
            name=name,
            email_address=email,
            password=hash_password(password),
        )
        session.add(new_admin_obj)
        session.commit()
        session.refresh(new_admin_obj)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Admin created successfully",
            "data": {
                "admin_id": str(new_admin_obj.admin_id),
                "name": new_admin_obj.name,
            },
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.warning("[new_admin] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def list_mail() -> Dict[str, Any]:
    """Return all active authorized email accounts.

    Returns:
        Dict with a list of auth mail summaries.

    Raises:
        ValueError: If no active auth mails exist.
    """
    session = SessionLocal()
    try:
        auth_mails = session.query(AuthMail).filter(AuthMail.is_active == True).all()
        if not auth_mails:
            raise ValueError("No auth mails found")
        return {
            "status": status.HTTP_200_OK,
            "message": "Auth mails retrieved successfully",
            "data": [
                {
                    "auth_mail_id": str(auth_mail.auth_mail_id),
                    "email_address": auth_mail.email_address,
                    "connect_with": auth_mail.connect_with,
                }
                for auth_mail in auth_mails
            ],
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("[mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def new_auth(payload: dict) -> Dict[str, Any]:
    """Register a new authorized email account for IMAP extraction.

    Args:
        payload: Dictionary with ``email``, optional ``imap_password``,
            and ``connect_with`` metadata.

    Returns:
        Dict with the newly created auth mail's ID and details.

    Raises:
        ValueError: If email is missing or already registered.
    """
    session = SessionLocal()
    try:
        email_address = payload.get("email")
        imap_password = payload.get("imap_password")
        connect_with = payload.get("connect_with", {})
        if not email_address:
            raise ValueError("Email must be provided")

        auth_mail = session.query(AuthMail).filter_by(email_address=email_address).first()
        if auth_mail:
            raise ValueError("Auth mail with this email already exists")
        new_auth_mail = AuthMail(
            email_address=email_address,
            imap_password=imap_password,
            connect_with=connect_with,
        )
        session.add(new_auth_mail)
        session.commit()
        session.refresh(new_auth_mail)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Auth mail created successfully",
            "data": {
                "auth_mail_id": str(new_auth_mail.auth_mail_id),
                "email_address": new_auth_mail.email_address,
                "connect_with": new_auth_mail.connect_with,
            },
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.warning("[new_auth] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def delete_auth_mail(auth_mail_id: str) -> Dict[str, Any]:
    """Soft-delete an authorized email account by setting ``is_active = False``.

    Args:
        auth_mail_id: UUID string of the auth mail to deactivate.

    Returns:
        Dict confirming deletion.

    Raises:
        ValueError: If the auth mail ID is not found.
    """
    session = SessionLocal()
    try:
        if not auth_mail_id or not auth_mail_id.strip():
            raise ValueError("auth_mail_id is required")

        auth_mail = session.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
        if not auth_mail:
            raise ValueError("Auth mail not found")
        auth_mail.is_active = False
        session.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "Auth mail deleted successfully",
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def update_auth_mail(auth_mail_id: str, payload: dict) -> Dict[str, Any]:
    """Update fields on an existing authorized email account.

    Only non-``None`` values in *payload* are applied.  Raises if the
    resulting email+password combination duplicates another record.

    Args:
        auth_mail_id: UUID string of the auth mail to update.
        payload: Dictionary of fields to update (``email``, ``imap_password``,
            ``connect_with``).

    Returns:
        Dict confirming the update.

    Raises:
        ValueError: If the record is not found or a duplicate is detected.
    """
    session = SessionLocal()
    try:
        if not auth_mail_id or not auth_mail_id.strip():
            raise ValueError("auth_mail_id is required")

        auth_mail = session.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
        if not auth_mail:
            raise ValueError("Auth mail not found")

        email_address = payload.get("email") if payload.get("email") else auth_mail.email_address
        imap_password = payload.get("imap_password") if payload.get("imap_password") else auth_mail.imap_password
        connect_with = payload.get("connect_with") if payload.get("connect_with") else auth_mail.connect_with

        duplicate = session.query(AuthMail).filter_by(email_address=email_address, imap_password=imap_password).first()
        if duplicate and str(duplicate.auth_mail_id) != auth_mail_id:
            raise ValueError("Auth mail with this email and IMAP password already exists, nothing to update")
        auth_mail.email_address = email_address
        auth_mail.imap_password = imap_password
        auth_mail.connect_with = connect_with
        session.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "Auth mail updated successfully",
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.warning("[update_auth_mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
#  1. Connected email accounts overview
# ═══════════════════════════════════════════════════════════════════════════

def list_email_accounts() -> Dict[str, Any]:
    """Return every AuthMail row with extraction-status fields.

    Returns:
        Dict containing a list of all email accounts and their status.
    """
    session = SessionLocal()
    try:
        accounts = session.query(AuthMail).all()
        return {
            "status": status.HTTP_200_OK,
            "message": "Email accounts retrieved",
            "data": [
                {
                    "auth_mail_id": str(a.auth_mail_id),
                    "email_address": a.email_address,
                    "is_active": a.is_active,
                    "is_blocked": a.is_blocked,
                    "extraction_enabled": a.extraction_enabled,
                    "last_extraction_at": a.last_extraction_at.isoformat() if a.last_extraction_at else None,
                    "connect_with": a.connect_with,
                }
                for a in accounts
            ],
        }
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
#  2 & 3. Per-account extraction / block toggles
# ═══════════════════════════════════════════════════════════════════════════

def toggle_extraction(auth_mail_id: str, enabled: bool) -> Dict[str, Any]:
    """Enable or disable extraction for a specific email account.

    Args:
        auth_mail_id: UUID string of the target email account.
        enabled: ``True`` to enable extraction, ``False`` to disable.

    Returns:
        Dict confirming the new extraction state.

    Raises:
        ValueError: If the account is not found.
    """
    session = SessionLocal()
    try:
        account = session.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
        if not account:
            raise ValueError("Email account not found")
        account.extraction_enabled = enabled
        session.commit()
        label = "enabled" if enabled else "disabled"
        return {"status": status.HTTP_200_OK, "message": f"Extraction {label}"}
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[toggle_extraction] %s", e, exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def toggle_block(auth_mail_id: str, blocked: bool) -> Dict[str, Any]:
    """Block or unblock a specific email account.

    Args:
        auth_mail_id: UUID string of the target email account.
        blocked: ``True`` to block, ``False`` to unblock.

    Returns:
        Dict confirming the new blocked state.

    Raises:
        ValueError: If the account is not found.
    """
    session = SessionLocal()
    try:
        account = session.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
        if not account:
            raise ValueError("Email account not found")
        account.is_blocked = blocked
        session.commit()
        label = "blocked" if blocked else "unblocked"
        return {"status": status.HTTP_200_OK, "message": f"Account {label}"}
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[toggle_block] %s", e, exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
#  4. Extraction config (global schedule / pause)
# ═══════════════════════════════════════════════════════════════════════════

def _get_or_create_config(session) -> "ExtractionConfig":
    """Fetch the active ExtractionConfig row, creating one with defaults if absent."""
    cfg = session.query(ExtractionConfig).filter(ExtractionConfig.is_active.is_(True)).first()
    if not cfg:
        cfg = ExtractionConfig(is_paused=False, interval_minutes=15)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


def get_extraction_config() -> Dict[str, Any]:
    """Retrieve the current global extraction schedule configuration.

    Returns:
        Dict with ``config_id``, ``is_paused``, and ``interval_minutes``.
    """
    session = SessionLocal()
    try:
        cfg = _get_or_create_config(session)
        return {
            "status": status.HTTP_200_OK,
            "message": "Extraction config retrieved",
            "data": {
                "config_id": str(cfg.config_id),
                "is_paused": cfg.is_paused,
                "interval_minutes": cfg.interval_minutes,
            },
        }
    finally:
        session.close()


def update_extraction_config(
    interval_minutes: Optional[int] = None,
    is_paused: Optional[bool] = None,
) -> Dict[str, Any]:
    """Update the global extraction schedule configuration.

    Args:
        interval_minutes: New polling interval (must be >= 1 if provided).
        is_paused: New paused state (if provided).

    Returns:
        Dict with the updated configuration values.

    Raises:
        ValueError: If *interval_minutes* is less than 1.
    """
    session = SessionLocal()
    try:
        cfg = _get_or_create_config(session)
        if interval_minutes is not None:
            if interval_minutes < 1:
                raise ValueError("Interval must be at least 1 minute")
            cfg.interval_minutes = interval_minutes
        if is_paused is not None:
            cfg.is_paused = is_paused
        session.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "Extraction config updated",
            "data": {
                "config_id": str(cfg.config_id),
                "is_paused": cfg.is_paused,
                "interval_minutes": cfg.interval_minutes,
            },
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[update_extraction_config] %s", e, exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def pause_extraction() -> Dict[str, Any]:
    """Globally pause all extraction jobs."""
    return update_extraction_config(is_paused=True)


def resume_extraction() -> Dict[str, Any]:
    """Globally resume all extraction jobs."""
    return update_extraction_config(is_paused=False)


# ═══════════════════════════════════════════════════════════════════════════
#  4b. Manual extraction trigger
# ═══════════════════════════════════════════════════════════════════════════

def trigger_extraction(auth_mail_id: Optional[str] = None) -> Dict[str, Any]:
    """Fire email extraction immediately.

    If *auth_mail_id* is supplied, validate the account is eligible first and
    stamp its ``last_extraction_at``.  The actual work is delegated to the
    existing ``fetch_emails()`` pipeline (which currently operates on the
    globally-configured mailbox).

    Args:
        auth_mail_id: Optional UUID of a specific account to extract.

    Returns:
        Dict with extraction result data.

    Raises:
        ValueError: If the account is not found, blocked, or has extraction
            disabled.
    """
    from src.services.email_reader.service import fetch_emails

    session = SessionLocal()
    try:
        if auth_mail_id:
            account = session.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
            if not account:
                raise ValueError("Email account not found")
            if account.is_blocked:
                raise ValueError("Account is blocked — cannot trigger extraction")
            if not account.extraction_enabled:
                raise ValueError("Extraction is disabled for this account")

        result = fetch_emails()

        if auth_mail_id:
            account = session.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
            if account:
                account.last_extraction_at = ist_now()
                session.commit()

        return {
            "status": status.HTTP_200_OK,
            "message": "Extraction triggered successfully",
            "data": result,
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.error("[trigger_extraction] %s", e, exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()
