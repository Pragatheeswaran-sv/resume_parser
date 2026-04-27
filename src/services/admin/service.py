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
from sqlalchemy import UUID, String, func, cast, inspect
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, Users, ExtractionConfig, ist_now
from src.auth.jwt import create_access_token, hash_password, verify_password
from fastapi import status
from src.admin.models import Admin, AiModel, AiModelConfig, AiModelversion, Users
from fastapi import  status
from src.utils.helper import encrypt_data, decrypt_data

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
                "is_admin": True,
                "name": admin.name,
                "email": admin.email_address,
                "is_admin": True,
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
# def profile():
    db = SessionLocal()
    try:
        if not admin_id:
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
        if not admin_id:
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
    in ``users`` and are not blocked.

    The frontend is responsible for verifying the user's identity with the
    SSO provider (Google / Zoho / Microsoft) before calling this function.
    This function normalises the provider name, validates the user against
    ``users``, and embeds SSO metadata into the JWT so downstream
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
            session.query(Users)
            .filter(
                Users.email_address == email,
                Users.is_active.is_(True),
                Users.is_blocked.is_(False),
            )
            .first()
        )
        if not account:
            raise ValueError("Access denied: email not approved or account blocked")

        token_payload: Dict[str, Any] = {
            "sub": str(account.user_id),
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

def list_mail(page, page_size, sort_by, sort_order, filter_column, filter_value) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size

        query = session.query(Users).filter(Users.is_active == True)

        filterable_columns = {
            "name": Users.name,
            "email": Users.email_address,
            "phone_number": Users.phone_number,
            "is_blocked": Users.is_blocked,
        }
        
        if filter_column and filter_value:
            column = filterable_columns.get(filter_column)

            if column is None:
                raise ValueError(f"Invalid filter column: {filter_column}")

            if hasattr(column.type, "python_type") and column.type.python_type == str:
                query = query.filter(column.ilike(f"%{filter_value}%"))
            else:
                query = query.filter(cast(column, String).ilike(f"%{filter_value}%"))

        if query.count() == 0:
            return{
                "status": status.HTTP_200_OK,
                "message": "No users found",
                "data": [],
            }

        sort_map = {
            "name": Users.name,
            "email": Users.email_address,
            "phone_number": Users.phone_number,
            "created_at": Users.created_at,
            "updated_at": Users.updated_at,
        }

        if sort_by in sort_map:
            sort_col = sort_map[sort_by]
            query = query.order_by(
                sort_col.desc() if sort_order == "desc" else sort_col.asc()
            )

        total_users = query.count()

        if total_users == 0:
            raise ValueError("No Users found")

        if offset >= total_users:
            raise ValueError("Invalid page number")

        users = query.limit(page_size).offset(offset).all()

        return {
            "status": status.HTTP_200_OK,
            "message": "Users retrieved successfully",
            "data": [
                {
                    "user_id": str(user.user_id),
                    "name": user.name,
                    "email_address": user.email_address,
                    "phone_number": user.phone_number,
                    "is_blocked": user.is_blocked,
                }
                for user in users
            ],
            "total_records": total_users,
        }

    except ValueError:
        raise
    except Exception as e:
        logger.warning("[mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()

def get_user(user_id):
    db = SessionLocal()
    try:
        if not user_id:
            raise ValueError("User ID not found")
        
        user  = db.query(Users).filter_by(user_id = user_id).first()
        
        return{
            "status": status.HTTP_200_OK,
            "message": "User profile retrieved successfully",
            
            "data" : {
                'admin_name' : user.name,
                'admin_email' : user.email_address,
                'admin_phone_number' : user.phone_number,
            }
        }
    except ValueError:
        raise
    except Exception as e:
        logger.warning("[admin_check] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

def get_user_by_id(user_id, admin_id):
    try:
        db = SessionLocal()
        admin = db.query(Admin).filter(admin_id == admin_id).first()
        if not admin:
            raise Exception("user has no access to delete account")
        
        user = db.query(Users).filter(Users.user_id == user_id, Users.is_active == True).first()
        if not user:
            raise Exception("User not found")
        
        return{
            "status": status.HTTP_200_OK,
            "message": "User retrieved successfully",
            "data": {
                "user_id": str(user.user_id),
                "name": user.name,
                "email_address": user.email_address,
                "phone_number": user.phone_number,
            },
        }
    except Exception as e:
        logger.warning("[particular_user] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

# def new_auth(payload: dict, admin_id) -> Dict[str, Any]:
def new_auth(payload: dict, admin_id) -> Dict[str, Any]:
    """Register a new authorized email account for IMAP extraction.

    Args:
        payload: Dictionary with ``email``, optional ``imap_password``,
            and ``connect_with`` metadata.

    Returns:
        Dict with the newly created User's ID and details.

    Raises:
        ValueError: If email is missing or already registered.
    """
    session = SessionLocal()   
    try:
        if not admin_id:
            raise ValueError("Admin ID must be provided")
        name = payload.get("name")
        email_address = payload.get("email")
        phone_number = payload.get("phone_number")

        if not email_address or not name or not phone_number or email_address.strip() == "" or name.strip() == "" or phone_number.strip() == "":
            raise ValueError("Email, name, and phone number are required")

        users = session.query(Users).filter_by(email_address=email_address).first()
        if users:
            raise ValueError("User with this email already exists")
        new_users = Users(
            name=name,
            email_address=email_address,
            phone_number=phone_number,
        )
        session.add(new_users)
        session.commit()
        session.refresh(new_users)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "User created successfully",
            "data": {
                "user_id": str(new_users.user_id),
                "name": new_users.name,
                "email_address": new_users.email_address,
                "phone_number": new_users.phone_number,
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


# def delete_user(user_id: str) -> Dict[str, Any]:
def delete_user(user_id: str, admin_id) -> Dict[str, Any]:
    """Soft-delete an authorized email account by setting ``is_active = False``.

    Args:
        user_id: UUID string of the User to deactivate.

    Returns:
        Dict confirming deletion.

    Raises:
        ValueError: If the User ID is not found.
    """
    session = SessionLocal()
    try:
        admin = session.query(Admin).filter(admin_id == admin_id).first()
        if not admin:
            raise Exception("user has no access to delete account")

        if not user_id or not user_id.strip():
            raise Exception("user_id is required")

        users = session.query(Users).filter_by(user_id=user_id, is_active = True).first()
        if not users:
            raise Exception("User not found")
        users.is_blocked = True
        users.is_active = False
        session.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "User deleted successfully",
        }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.warning("[delete_user] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


def update_user(payload: dict, user_id: str, admin_id) -> Dict[str, Any]:
    """Update fields on an existing authorized email account.

    Only non-``None`` values in *payload* are applied.  Raises if the
    resulting email+password combination duplicates another record.

    Args:
        user_id: UUID string of the User to update.
        payload: Dictionary of fields to update (``email``, ``imap_password``,
            ``connect_with``).

    Returns:
        Dict confirming the update.

    Raises:
        ValueError: If the record is not found or a duplicate is detected.
    """
    session = SessionLocal()
    try:
        if not user_id:
            raise ValueError("user_id is required")

        users = session.query(Users).filter_by(user_id=user_id).first()
        if not users:
            raise ValueError("User not found")

        name = payload.get("name") or users.name
        email_address = payload.get("email") if payload.get("email") else users.email_address
        imap_password = payload.get("imap_password") if payload.get("imap_password") else users.imap_password
        connect_with = payload.get("connect_with") if payload.get("connect_with") else users.connect_with
        blocked = payload.get("is_blocked") if payload.get("is_blocked") is not None else users.is_blocked
        phone_number = payload.get("phone_number") if payload.get("phone_number") else users.phone_number
        admin = session.query(Admin).filter(admin_id == admin_id).first()

        if not admin:
            raise Exception("user has no access to enable/disable account")
        if "is_blocked" in payload:
            if blocked == True:
                users.is_blocked = blocked
                session.commit()
                return {
                    "status": status.HTTP_200_OK,
                    "message": "User deactivated successfully",
                }
            elif blocked == False:
                users.is_blocked = blocked
                session.commit()
                return {
                    "status": status.HTTP_200_OK,
                    "message": "User activated successfully",
                }
            
        if users:
            duplicate = session.query(Users).filter_by(email_address=email_address, phone_number=phone_number).first()
            if duplicate and str(duplicate.user_id) != user_id:
                raise ValueError("User with this email and phone number already exists, nothing to update")
            users.name = name
            users.email_address = email_address
            users.imap_password = imap_password
            users.phone_number = phone_number
            users.connect_with = connect_with
            session.commit()
            return {
                "status": status.HTTP_200_OK,
                "message": "User updated successfully",
            }
    except ValueError:
        raise
    except Exception as e:
        session.rollback()
        logger.warning("[update_user] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
#  1. Connected email accounts overview
# ═══════════════════════════════════════════════════════════════════════════

def list_email_accounts() -> Dict[str, Any]:
    """Return every Users row with extraction-status fields.

    Returns:
        Dict containing a list of all email accounts and their status.
    """
    session = SessionLocal()
    try:
        accounts = session.query(Users).all()
        return {
            "status": status.HTTP_200_OK,
            "message": "Email accounts retrieved",
            "data": [
                {
                    "user_id": str(a.user_id),
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

def toggle_extraction(user_id: str, enabled: bool) -> Dict[str, Any]:
    """Enable or disable extraction for a specific email account.

    Args:
        user_id: UUID string of the target email account.
        enabled: ``True`` to enable extraction, ``False`` to disable.

    Returns:
        Dict confirming the new extraction state.

    Raises:
        ValueError: If the account is not found.
    """
    session = SessionLocal()
    try:
        account = session.query(Users).filter_by(user_id=user_id).first()
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


def toggle_block(user_id: str, blocked: bool) -> Dict[str, Any]:
    """Block or unblock a specific email account.

    Args:
        user_id: UUID string of the target email account.
        blocked: ``True`` to block, ``False`` to unblock.

    Returns:
        Dict confirming the new blocked state.

    Raises:
        ValueError: If the account is not found.
    """
    session = SessionLocal()
    try:
        account = session.query(Users).filter_by(user_id=user_id).first()
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
                "schedule_type": cfg.schedule_type,
                "weekday": cfg.weekday
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
                "schedule_type": cfg.schedule_type,
                "weekday": cfg.weekday
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
    schedule_type: Optional[str] = None,
    weekday: Optional[str] = None
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
        
        if schedule_type:
            cfg.schedule_type = schedule_type
        
        if weekday:
            cfg.weekday = weekday

        # if schedule_type is None:
        #     raise ("Shedule_type should not be None")
        
        # if weekday == "":
        #     raise ("weekdat should not be empty")

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
                "schedule_type" : cfg.schedule_type,
                "weekday": cfg.weekday
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

def trigger_extraction(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Fire email extraction immediately.

    If *user_id* is supplied, validate the account is eligible first and
    stamp its ``last_extraction_at``.  The actual work is delegated to the
    existing ``fetch_emails()`` pipeline (which currently operates on the
    globally-configured mailbox).

    Args:
        user_id: Optional UUID of a specific account to extract.

    Returns:
        Dict with extraction result data.

    Raises:
        ValueError: If the account is not found, blocked, or has extraction
            disabled.
    """
    from src.services.email_reader.service import fetch_emails

    session = SessionLocal()
    try:
        if user_id:
            account = session.query(Users).filter_by(user_id=user_id).first()
            if not account:
                raise ValueError("Email account not found")
            if account.is_blocked:
                raise ValueError("Account is blocked — cannot trigger extraction")
            if not account.extraction_enabled:
                raise ValueError("Extraction is disabled for this account")

        result = fetch_emails()

        if user_id:
            account = session.query(Users).filter_by(user_id=user_id).first()
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

def new_job(payload, admin_id):
    try:
        payload = payload.dict()
        db =SessionLocal()

        admin = db.query(Admin).filter(admin_id == admin_id).first()
        if not admin:
            raise Exception("User are restricted to schedule job")
        
        duplicate = db.query(ExtractionConfig).all()
        if len(duplicate) > 1:
            raise Exception("can't create more than one job")
        
        interval_minutes = payload.get('interval_minutes') or None
        is_paused = payload.get('is_paused') or None
        window_enabled = payload.get('window_enabled') or None
        window_start_time = payload.get('window_start_time') or None
        window_timezone = payload.get('window_timezone') or None
        schedule_type = payload.get('schedule_type') or None
        weekday = payload.get('weekday') or None

        if window_enabled and not window_start_time:
            raise Exception("window_start_time required when window is enabled")

        if schedule_type == "weekly" and not weekday:
            raise Exception("weekday required for weekly schedule")
        
        job = ExtractionConfig(
            interval_minutes = interval_minutes,
            is_paused = is_paused,
            window_enabled = window_enabled,
            window_start_time = window_start_time,
            # window_timezone = window_timezone,
            schedule_type = schedule_type,
            weekday = weekday
        )

        db.add(job)
        db.commit()
        db.refresh(job)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Job created successfully",
            "data": {
                "config_id": str(job.config_id),
            },
        }
    except Exception as e:
        logger.warning("[new_job] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

    
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
            raise ValueError("Provided model name")

        existing_model = (
            db.query(AiModel)
            .filter(AiModel.model_name == model_name, AiModel.is_active == True)
            .first()
        )
        if not existing_model:
            new_model = AiModel(model_name=model_name)
            db.add(new_model)
            db.commit()
            db.refresh(new_model)
            model_id = new_model.ai_model_id
            model_name = new_model.model_name
        else:
            model_id = existing_model.ai_model_id
            model_name = existing_model.model_name

        version_name = payload.get("version_name") if payload.get("version_name") else None
        
        version = db.query(AiModelversion).filter_by(version_name = version_name, is_active = True).first()
        if version:
            raise ValueError("Model version with this name already exists")
        
        if not version_name or version_name.strip() == "" or version_name == None:
            raise ValueError("Provided version name")
        
        new_version = AiModelversion(
            ai_model_id = model_id,
            version_name = version_name,
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model created successfully",
            "data": {
                "model_id": str(model_id),
                "model_name": model_name,
                "model_version_id": str(new_version.ai_model_version_id),
                "version_name": new_version.version_name,
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

# def new_model_version(model_id, payload):
#     try:
#         db = SessionLocal()
#         model_id = str(model_id)
#         version_name = payload.get("version_name") if payload.get("version_name") else None
        
#         model = db.query(AiModel).filter_by(ai_model_id=model_id, is_active=True).first()
#         if not model:
#             raise ValueError("No model found for the given model ID")
        
#         if not version_name or version_name.strip() == "" or version_name == None:
#             raise ValueError("Version name must be provided")
        
#         new_version = AiModelversion(
#             ai_model_id = model_id,
#             version_name = version_name,
#         )
#         db.add(new_version)
#         db.commit()
#         db.refresh(new_version)
#         return {
#             "status": status.HTTP_201_CREATED,
#             "message": "Model version created successfully",
#             "data": {
#                 "model_version_id": str(new_version.ai_model_version_id),
#                 "version_name": new_version.version_name,
#             }
#         }             
#     except Exception as e:
#         logger.warning("[new_model_version] Error: %s", str(e), exc_info=True)
#         raise ValueError(str(e))  
#     finally:
#         db.close()  

# def model_config(payload, admin_id):
def model_config(payload, admin_id):
    try:
        db = SessionLocal()
        model_version_id = payload.get("model_version_id") 
        ai_model_id = payload.get("model_id") 
        apikey = payload.get("apikey") if payload.get("apikey") else None
        version = payload.get("version") if payload.get("version") else None
        max_tokens = payload.get("max_tokens") if payload.get("max_tokens") else None
        temperature = payload.get("temperature") if payload.get("temperature") else None
        if not admin_id:
            raise ValueError("Admin ID must be provided")
        
        model = db.query(AiModel).filter_by(ai_model_id=ai_model_id, is_active=True).first()
        if not model:
            raise ValueError("No model found for the given model ID")

        model_version = db.query(AiModelversion).filter_by(ai_model_version_id=model_version_id, is_active=True).first()
        if not model_version:
            raise ValueError("No model version found for the given model version ID")
        
        duplicate_config = db.query(AiModelConfig).filter_by(ai_model_version_id = model_version_id, ai_model_id = ai_model_id, apikey = apikey).first()
        if duplicate_config:
            raise ValueError("Model with APIKEY is already exist")
        
        encrtyped_key = encrypt_data(apikey)
        if not encrtyped_key:
            raise ValueError("Error encrypting API key")
        
        new_config = AiModelConfig(
            ai_model_version_id = model_version_id,
            ai_model_id = ai_model_id,
            admin_id = admin_id,
            apikey = encrtyped_key,
            version = version,
            max_tokens = max_tokens,
            is_active = False
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
                "apikey": decrypt_data(new_config.apikey),
                "max_tokens": new_config.max_tokens,
            }
        }             
    except Exception as e:
        logger.warning("[model_config] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()
    
def get_model(page, page_size, sort_by, sort_order, filter_column, filter_value, admin_id):
    db = SessionLocal()
    try:
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size

        if not admin_id:
            raise ValueError("Admin ID must be provided")

        def _mask_apikey(raw_apikey):
            if not raw_apikey:
                return None

            normalized_key = decrypt_data(raw_apikey)
            if normalized_key is None:
                normalized_key = raw_apikey

            normalized_key = str(normalized_key)
            if not normalized_key:
                return None

            if len(normalized_key) <= 4:
                return "*" * len(normalized_key)
            return normalized_key[:2] + "******" + normalized_key[-2:]

        query = (
            db.query(
                func.json_build_object(
                    'model_config_id', AiModelConfig.ai_model_config_id,
                    'model_id', AiModelConfig.ai_model_id,
                    'model_name', AiModel.model_name,
                    'model_version_id', AiModelConfig.ai_model_version_id,
                    'model_version_name', AiModelversion.version_name,
                    'admin_id', AiModelConfig.admin_id,
                    'apikey', AiModelConfig.apikey,
                    'max_tokens', AiModelConfig.max_tokens,
                    'temperature', AiModelConfig.temparature,
                    'is_active', AiModelConfig.is_active
                )
            )
            .select_from(AiModelConfig)
            .join(AiModel, AiModel.ai_model_id == AiModelConfig.ai_model_id)
            .join(AiModelversion, AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id)
            .filter(AiModelConfig.admin_id == admin_id)
        )

        filterable_columns = {
            "model_config_id": AiModelConfig.ai_model_config_id,
            "model_id": AiModelConfig.ai_model_id,
            "model_name": AiModel.model_name,
            "model_version_id": AiModelConfig.ai_model_version_id,
            "model_version_name": AiModelversion.version_name,
            "admin_id": AiModelConfig.admin_id,
            "apikey": AiModelConfig.apikey,
            "max_tokens": AiModelConfig.max_tokens,
            "temperature": AiModelConfig.temparature,
            "is_active": AiModelConfig.is_active
        }

        if filter_column and filter_value:
            column = filterable_columns.get(filter_column)

            if column is None:
                raise ValueError(f"Invalid filter column: {filter_column}")

            if hasattr(column.type, "python_type") and column.type.python_type == str:
                query = query.filter(column.ilike(f"%{filter_value}%"))
            else:
                query = query.filter(cast(column, String).ilike(f"%{filter_value}%"))

            if query.count() == 0:
                return {
                    "status": status.HTTP_200_OK,
                    "message": "No config model found",
                    "data": []
                }

        sort_map = {
            "name": AiModel.model_name,
            "version_name": AiModelversion.version_name,
            "api_key": AiModelConfig.apikey,
            "max_tokens": AiModelConfig.max_tokens,
            "temperature": AiModelConfig.temparature,
            "created_at": AiModelConfig.created_at,
            "updated_at": AiModelConfig.updated_by,
        }

        if sort_by and sort_by in sort_map:
            sort_col = sort_map[sort_by]
            sort_order = (sort_order or "asc").lower()

            query = query.order_by(
                sort_col.desc() if sort_order == "desc" else sort_col.asc()
            )

        total_record = query.count()

        if total_record == 0:
            raise ValueError("No model config found for the given admin ID")

        if offset >= total_record:
            raise ValueError("Invalid page number")

        model_config = query.limit(page_size).offset(offset).all()
        data = []

        for config in model_config:
            masked_api_key = _mask_apikey(config[0]['apikey'])

            data.append({
                "config_id": config[0]['model_config_id'],
                "model_id": config[0]['model_id'],
                "model_name": config[0]['model_name'],
                "version_id": config[0]['model_version_id'],
                "version_name": config[0]['model_version_name'],
                "apikey": masked_api_key,
                "max_tokens": config[0]['max_tokens'],
                "admin_id": config[0]['admin_id'],
                "is_active": config[0]['is_active'],
            })

        return {
            "status": status.HTTP_200_OK,
            "message": "Model config retrieved successfully",
            "data": data,
            "total_record": total_record
        }

    except Exception as e:
        logger.warning("[get_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

def toggle_model(model_config_id, admin_id):
    try:
        db = SessionLocal()
        if not admin_id:
            raise ValueError("Admin ID must be provided")
        
        disable_all = db.query(AiModelConfig).filter(
            AiModelConfig.ai_model_config_id != model_config_id
            ).update(
                {AiModelConfig.is_active: False},
                synchronize_session=False
            )
        
        enable_one = db.query(AiModelConfig).filter(
                AiModelConfig.ai_model_config_id == model_config_id
            ).update(
                {AiModelConfig.is_active: True},
                synchronize_session=False
            )
        db.commit()

        active_model = db.query(AiModelConfig).all()
        data = []
        for active in active_model:
            decrypted_key = None
            masked_api_key = None

            if active.apikey:
                try:
                    decrypted_key = decrypt_data(active.apikey)
                except Exception:
                    decrypted_key = str(active.apikey)  # fallback (plain text or invalid)

            if decrypted_key and isinstance(decrypted_key, str):
                if len(decrypted_key) > 4:
                    masked_api_key = (
                        decrypted_key[:2] + "******" + decrypted_key[-2:]
                    )
                else:
                    masked_api_key = "******"
            else:
                masked_api_key = None

            data.append({
                "config_id": active.ai_model_config_id,
                "model_id": active.ai_model_id,
                "version_id": active.ai_model_version_id,
                "apikey": masked_api_key,
                "max_tokens": active.max_tokens,
                "admin_id": active.admin_id,
                "is_active": active.is_active,
            })
        return {
            "status": status.HTTP_200_OK,
            "message": "Model enabled successfully",
            "data": data
        }
    except Exception as e:
        logger.warning("[enable/disable model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()
