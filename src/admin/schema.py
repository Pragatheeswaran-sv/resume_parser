from pydantic import BaseModel, field_validator
from typing import Literal, Optional


# ── Auth / JWT ────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    email: str
    password: str

class AdminUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None

class SSOLoginRequest(BaseModel):
    """Payload sent by the frontend after the user authenticates with the
    SSO provider.  The ``email`` field is the verified identity from the
    SSO token; ``provider`` identifies the authentication origin.

    Supported providers: ``"google"``, ``"zoho"``, ``"microsoft"``.
    When omitted the login is treated as a generic SSO login.
    """
    email: str
    provider: Optional[Literal["google", "zoho", "microsoft"]] = None

    @field_validator("email")
    @classmethod
    def email_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Email must not be empty")
        return v.strip().lower()


class RefreshTokenRequest(BaseModel):
    """Body for ``POST /api/auth/refresh`` and ``POST /api/auth/logout``."""
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    role: str
    name: Optional[str] = None
    email: Optional[str] = None
    provider: Optional[str] = None


# ── Admin ────────────────────────────────────────────────────────────────

class AdminCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class AdminLoginResponse(BaseModel):
    name: str
    email_address: str


# ── Users (connected email accounts) ─────────────────────────────────

class AuthorizedUserCreate(BaseModel):
    name: str
    email: str
    phone_number: str


class AuthorizedUserUpdate(BaseModel):
    name: str | None = None
    email: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None
    phone_number: Optional[str] = None
    connect_with: Optional[dict] = None
    is_blocked : Optional[bool] = None


class EmailAccountResponse(BaseModel):
    user_id: str
    email_address: Optional[str] = None
    is_active: bool
    is_blocked: bool
    extraction_enabled: bool
    last_extraction_at: Optional[str] = None
    connect_with: Optional[str] = None


class ExtractionToggleRequest(BaseModel):
    extraction_enabled: bool


class BlockToggleRequest(BaseModel):
    is_blocked: bool


# ── Extraction config (global control) ──────────────────────────────────

class ExtractionConfigResponse(BaseModel):
    config_id: str
    is_paused: bool
    interval_minutes: int
    window_enabled: bool
    window_start_time: Optional[str] = None
    window_end_time: Optional[str] = None
    window_timezone: str
    schedule_type: Optional[str] = None
    weekday: Optional[str] = None


class ExtractionConfigUpdate(BaseModel):
    interval_minutes: Optional[int] = None
    is_paused: Optional[bool] = None
    window_enabled: Optional[bool] = None
    window_start_time: Optional[str] = None
    window_end_time: Optional[str] = None
    window_timezone: Optional[str] = None
    schedule_type: Optional[str] = None
    weekday: Optional[str] = None

class Validate_new_job(BaseModel):
    interval_minutes: int
    is_paused: bool
    window_enabled: bool
    window_start_time: str
    # window_end_time: str
    # window_timezone: Optional[str]
    schedule_type: str
    weekday: str

class CreateModelValidate(BaseModel):
    model_name : str
    version_name : str 

# ── Generic response helpers ─────────────────────────────────────────────

class StatusResponse(BaseModel):
    status: int
    message: str


class DataResponse(StatusResponse):
    data: Optional[object] = None
