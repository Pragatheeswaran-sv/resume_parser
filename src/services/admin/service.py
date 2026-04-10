"""Admin service layer.

Business logic for administrator accounts, authorized email management,
and global extraction configuration.  Every public function uses its own
database session and raises ``ValueError`` on validation failures so the
API layer can translate them into appropriate HTTP responses.
"""

from typing import Any, Dict, List, Optional
import logging
import datetime

import json

from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import UUID, func, cast
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, AuthMail, ExtractionConfig, ist_now
from src.auth.jwt import create_access_token, hash_password, verify_password
from fastapi import status
from src.admin.models import Admin, AiModel, AiModelConfig, AiModelversion, AuthMail
from fastapi import  status

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
        
        if email == "" or password == "" or not email or not password:
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

def profile(admin_id):
    db = SessionLocal()
    try:
        if not admin_id or not admin_id.strip():
            raise ValueError("Admin ID must be provided")
        
        admin  = db.query(Admin).filter_by(admin_id = admin_id ).first()
        if not admin:
            raise ValueError("Admin not found")
        return{
            "status": status.HTTP_200_OK,
            "message": "Admin profile retrieved successfully",
            
            "data" : {
                'admin_name' : admin.name,
                'admin_email' : admin.email_address,
                'admin_phone_number' : admin.phone_number,
            }
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("[admin_check] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

def update_admin_profile(admin_id, payload):
    db = SessionLocal()
    try:
        if not admin_id or not admin_id.strip():
            raise ValueError("Admin ID must be provided")
        
        admin  = db.query(Admin).filter_by(admin_id = admin_id ).first()
        if not admin:
            raise ValueError("Admin not found")
        
        name = payload.get("name") if payload.get("name") else admin.name
        phone_number = payload.get("phone_number") if payload.get("phone_number") else admin.phone_number
        old_password = payload.get("old_password")

        if name == admin.name and phone_number == admin.phone_number and not payload.get("new_password"):
            raise ValueError("No changes detected in the profile update")
        
        if not old_password or old_password.strip() == "":
            raise ValueError("Old password is required to update profile")
        new_password = payload.get("new_password") if payload.get("new_password") else None
        is_password = verify_password(old_password, admin.password) if admin.password else False

        if not is_password:
            raise ValueError("Old password is incorrect")
        
        if new_password:
            admin.password = hash_password(new_password)

        admin.name = name
        admin.phone_number = phone_number
        db.commit()
        return{
            "status": status.HTTP_200_OK,
            "message": "Admin profile updated successfully",
            
            "data" : {
                'admin_name' : admin.name,
                'admin_email' : admin.email_address,
                'admin_phone_number' : admin.phone_number,
            }
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("[update_admin_profile] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

SUPPORTED_SSO_PROVIDERS = {"google", "zoho", "microsoft"}


def sso_user_login(
    email: str,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Issue a JWT for an SSO-authenticated user after verifying they exist
    in ``auth_mail`` and are not blocked.

    The frontend is responsible for verifying the user's identity with the
    SSO provider (Google / Zoho / Microsoft) before calling this function.
    This function normalises the provider name, validates the user against
    ``auth_mail``, and embeds SSO metadata into the JWT so downstream
    services know the authentication origin.

    Args:
        email: Verified email from the SSO provider.
        provider: Optional SSO provider identifier (e.g. ``"google"``,
            ``"zoho"``, ``"microsoft"``).  Normalised to lowercase.

    Returns:
        Dict containing an access token and user profile info.

    Raises:
        ValueError: If the email is empty, the provider is unsupported,
            the email is not approved, or the account is blocked.
    """
    session = SessionLocal()
    try:
        if not email or not email.strip():
            raise ValueError("Email must be provided")
        email = email.strip().lower()

        normalized_provider: Optional[str] = None
        if provider:
            normalized_provider = provider.strip().lower()
            if normalized_provider not in SUPPORTED_SSO_PROVIDERS:
                raise ValueError(
                    f"Unsupported SSO provider: {provider}. "
                    f"Supported providers: {', '.join(sorted(SUPPORTED_SSO_PROVIDERS))}"
                )

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

        token_payload: Dict[str, Any] = {
            "sub": str(account.auth_mail_id),
            "email": account.email_address,
            "role": "user",
        }
        if normalized_provider:
            token_payload["provider"] = normalized_provider

        token = create_access_token(token_payload)

        response_data: Dict[str, Any] = {
            "access_token": token,
            "token_type": "bearer",
            "role": "user",
            "email": account.email_address,
        }
        if normalized_provider:
            response_data["provider"] = normalized_provider

        return {
            "status": status.HTTP_200_OK,
            "message": "User logged in successfully",
            "data": response_data,
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
        
        # data = request.json()
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
#  Time-window evaluation
# ═══════════════════════════════════════════════════════════════════════════

def is_within_extraction_window(config: Optional[Dict[str, Any]] = None) -> bool:
    """Check whether the current time falls within the configured extraction window.

    When ``window_enabled`` is False (or *config* is None / missing the key),
    execution is always allowed.  Supports cross-midnight windows such as
    22:00 → 08:00.  The interval is **[start, end)** — inclusive of start,
    exclusive of end.

    Args:
        config: Dict with window fields.  If None the active config is loaded
                from the database automatically.

    Returns:
        True if execution is allowed, False otherwise.
    """
    if config is None:
        session = SessionLocal()
        try:
            cfg = session.query(ExtractionConfig).filter(
                ExtractionConfig.is_active.is_(True)
            ).first()
            if not cfg:
                logger.info("No active extraction config found — window check passes")
                return True
            config = {
                "window_enabled": cfg.window_enabled,
                "window_start_time": cfg.window_start_time,
                "window_end_time": cfg.window_end_time,
                "window_timezone": cfg.window_timezone,
            }
        finally:
            session.close()

    if not config.get("window_enabled"):
        logger.info("Time window is disabled — execution allowed")
        return True

    tz_name = config.get("window_timezone") or "Asia/Kolkata"
    start_str = config.get("window_start_time")
    end_str = config.get("window_end_time")

    if not start_str or not end_str:
        logger.warning(
            "Time window enabled but start/end not configured — allowing execution"
        )
        return True

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.error("Invalid timezone '%s' — allowing execution as fallback", tz_name)
        return True

    now = datetime.datetime.now(tz).time()
    start_time = datetime.time.fromisoformat(start_str)
    end_time = datetime.time.fromisoformat(end_str)

    if start_time < end_time:
        allowed = start_time <= now < end_time
    else:
        allowed = now >= start_time or now < end_time

    logger.info(
        "Time window check: now=%s, window=[%s, %s), timezone=%s, allowed=%s",
        now.strftime("%H:%M:%S"),
        start_str,
        end_str,
        tz_name,
        allowed,
    )
    return allowed


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
        Dict with ``config_id``, ``is_paused``, ``interval_minutes``,
        and time-window fields.
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
                "window_enabled": cfg.window_enabled or False,
                "window_start_time": cfg.window_start_time,
                "window_end_time": cfg.window_end_time,
                "window_timezone": cfg.window_timezone or "Asia/Kolkata",
            },
        }
    finally:
        session.close()


def update_extraction_config(
    interval_minutes: Optional[int] = None,
    is_paused: Optional[bool] = None,
    window_enabled: Optional[bool] = None,
    window_start_time: Optional[str] = None,
    window_end_time: Optional[str] = None,
    window_timezone: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the global extraction schedule configuration.

    Args:
        interval_minutes: New polling interval (must be >= 1 if provided).
        is_paused: New paused state (if provided).
        window_enabled: Enable or disable time-window restriction.
        window_start_time: Window start in ``"HH:MM"`` format.
        window_end_time: Window end in ``"HH:MM"`` format.
        window_timezone: IANA timezone name (e.g. ``"Asia/Kolkata"``).

    Returns:
        Dict with the updated configuration values.

    Raises:
        ValueError: If *interval_minutes* is less than 1 or time format is invalid.
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

        if window_enabled is not None:
            cfg.window_enabled = window_enabled
        if window_start_time is not None:
            datetime.time.fromisoformat(window_start_time)
            cfg.window_start_time = window_start_time
        if window_end_time is not None:
            datetime.time.fromisoformat(window_end_time)
            cfg.window_end_time = window_end_time
        if window_timezone is not None:
            ZoneInfo(window_timezone)
            cfg.window_timezone = window_timezone

        session.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "Extraction config updated",
            "data": {
                "config_id": str(cfg.config_id),
                "is_paused": cfg.is_paused,
                "interval_minutes": cfg.interval_minutes,
                "window_enabled": cfg.window_enabled or False,
                "window_start_time": cfg.window_start_time,
                "window_end_time": cfg.window_end_time,
                "window_timezone": cfg.window_timezone or "Asia/Kolkata",
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

    
def list_model():
    try:
        db = SessionLocal()
        models = db.query(AiModel).filter(AiModel.is_active == True).all()
        if not models:
            raise ValueError("No models found")
        
        return {
            "status": status.HTTP_200_OK,
            "message": "Models retrieved successfully",
            "data": [
                {
                    "model_id": model.ai_model_id,
                    "model_name": model.model_name,
                }
                for model in models
            ]
        }
    except Exception as e:
        logger.warning("[list_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()
    
def create_model(payload):
    """Create a new AI model entry.

    Returns a standard response dict with ``status``, ``message``, and created model ``data``.
    Raises ``ValueError`` for invalid payload or duplicate model names.
    """
    try:
        db = SessionLocal()
        model_name = (payload.get("model_name") or "").strip()

        if not model_name:
            raise ValueError("Model name must be provided")

        existing_model = (
            db.query(AiModel)
            .filter(AiModel.model_name == model_name, AiModel.is_active == True)
            .first()
        )
        if existing_model:
            raise ValueError("Model with this name already exists")

        new_model = AiModel(model_name=model_name)
        db.add(new_model)
        db.commit()
        db.refresh(new_model)

        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model created successfully",
            "data": {
                "model_id": str(new_model.ai_model_id),
                "model_name": new_model.model_name,
            },
        }
    except Exception as e:
        logger.warning("[create_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

def model_version(model_id):
    try:
        db = SessionLocal()
        id = str(model_id)
        # print(type())
        model = db.query(AiModel).filter_by(ai_model_id=id, is_active=True).all()
        if not model:
            raise ValueError("No model found for the given model ID")
        model_versions = db.query(AiModelversion).filter_by(ai_model_id=id, is_active=True).all()
        if not model_versions:
            raise ValueError("No model versions found for the given model ID")
        return {
            "status": status.HTTP_200_OK,
            "message": "Model versions retrieved successfully",
            "data": [
                {
                    "model_version_id": str(model_version.ai_model_version_id),
                    "version_name": model_version.version_name,
                }
                for model_version in model_versions
            ]
        }             
    except Exception as e:
        logger.warning("[model_version] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

def new_model_version(model_id, payload):
    try:
        db = SessionLocal()
        model_id = str(model_id)
        version_name = payload.get("version_name") if payload.get("version_name") else None
        
        model = db.query(AiModel).filter_by(ai_model_id=model_id, is_active=True).first()
        if not model:
            raise ValueError("No model found for the given model ID")
        
        if not version_name or version_name.strip() == "" or version_name == None:
            raise ValueError("Version name must be provided")
        
        # version_name = f"{model.model_name}_v{len(db.query(AiModelversion).filter_by(ai_model_id=model_id).all()) + 1}"
        new_version = AiModelversion(
            ai_model_id = model_id,
            version_name = version_name
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model version created successfully",
            "data": {
                "model_version_id": str(new_version.ai_model_version_id),
                "version_name": new_version.version_name,
            }
        }             
    except Exception as e:
        logger.warning("[new_model_version] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))  
    finally:
        db.close()  

def model_config(payload, admin_id):
    try:
        db = SessionLocal()
        model_version_id = payload.get("model_version_id") 
        ai_model_id = payload.get("model_id") 
        print(ai_model_id)
        apikey = payload.get("apikey") if payload.get("apikey") else None
        print(apikey)
        version = payload.get("version") if payload.get("version") else None
        print(version)
        max_tokens = payload.get("max_tokens") if payload.get("max_tokens") else None
        print(max_tokens)
        temperature = payload.get("temperature") if payload.get("temperature") else None
        print(temperature)
        if not admin_id:
            raise ValueError("Admin ID must be provided")
        
        model = db.query(AiModel).filter_by(ai_model_id=ai_model_id, is_active=True).first()
        if not model:
            raise ValueError("No model found for the given model ID")

        model_version = db.query(AiModelversion).filter_by(ai_model_version_id=model_version_id, is_active=True).first()
        if not model_version:
            raise ValueError("No model version found for the given model version ID")
        
        
        new_config = AiModelConfig(
            ai_model_version_id = model_version_id,
            ai_model_id = ai_model_id,
            admin_id = admin_id,
            apikey = apikey,
            version = version,
            max_tokens = max_tokens
        )
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model config created successfully",
            "data": {
                "model_config_id": str(new_config.ai_model_config_id),
                "model_id": str(new_config.ai_model_id),
                "model_name" : model.model_name,
                "model_version_id": str(new_config.ai_model_version_id),
                "model_version_name": model_version.version_name,
                "admin_id": str(new_config.admin_id),
                "apikey": new_config.apikey,
                "max_tokens": new_config.max_tokens,
            }
        }             
    except Exception as e:
        logger.warning("[model_config] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()
    
def get_model(admin_id):
    try:
        db = SessionLocal()
        if not admin_id:
            raise ValueError("Admin ID must be provided")

        model_config =( db.query(
            func.json_build_object(
                'model_config_id', AiModelConfig.ai_model_config_id,
                'model_id', AiModelConfig.ai_model_id,
                'model_name', AiModel.model_name,
                'model_version_id', AiModelConfig.ai_model_version_id,
                'model_version_name', AiModelversion.version_name,
                'admin_id', AiModelConfig.admin_id,
                'apikey', AiModelConfig.apikey,
                'max_tokens', AiModelConfig.max_tokens,
                'temparature', AiModelConfig.temparature,
            )
        )
        .select_from(AiModelConfig).
        join(AiModel, AiModel.ai_model_id == AiModelConfig.ai_model_id).
        join(AiModelversion, AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id).
        filter(AiModelConfig.admin_id == admin_id, AiModelConfig.is_active == True).
        first())
        
        if not model_config:
            raise ValueError("No model config found for the given admin ID")
        
        return{
            "status": status.HTTP_200_OK,
            "message": "Model config retrieved successfully",
            "data": model_config[0] if model_config else None
        }             
    except Exception as e:
        logger.warning("[get_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()