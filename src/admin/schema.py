from pydantic import BaseModel
from typing import Optional


# ── Auth / JWT ────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    email: str
    password: str


class SSOLoginRequest(BaseModel):
    """Payload sent by the frontend after the user authenticates with the
    SSO provider.  The ``email`` field is the verified identity from the
    SSO token; ``provider`` is optional metadata (e.g. "google", "azure").
    """
    email: str
    provider: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: Optional[str] = None
    email: str


# ── Admin ────────────────────────────────────────────────────────────────

class AdminCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class AdminLoginResponse(BaseModel):
    name: str
    email_address: str


# ── AuthMail (connected email accounts) ─────────────────────────────────

class AuthorizedUserCreate(BaseModel):
    email: str
    imap_password: Optional[str] = None
    connect_with: str


class EmailAccountResponse(BaseModel):
    auth_mail_id: str
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


class ExtractionConfigUpdate(BaseModel):
    interval_minutes: Optional[int] = None
    is_paused: Optional[bool] = None


# ── Generic response helpers ─────────────────────────────────────────────

class StatusResponse(BaseModel):
    status: int
    message: str


class DataResponse(StatusResponse):
    data: Optional[object] = None
