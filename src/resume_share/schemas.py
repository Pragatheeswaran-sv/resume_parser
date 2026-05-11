from typing import List, Optional
from pydantic import BaseModel, EmailStr


class ShareResumeRequest(BaseModel):
    candidate_id: str
    resume_id: str
    to_address: EmailStr
    cc_address: Optional[List[EmailStr]] = None
    share: bool


class ShareResumeResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[str] = None


# ── Email Provider Config ────────────────────────────────────────────────

class EmailProviderConfigCreate(BaseModel):
    provider_name: str
    from_email: EmailStr
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    tls_enabled: Optional[bool] = True
    active: Optional[bool] = False


class EmailProviderConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    from_email: Optional[EmailStr] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    tls_enabled: Optional[bool] = None
    active: Optional[bool] = None


# ── Email Template ───────────────────────────────────────────────────────

class EmailTemplateCreate(BaseModel):
    template_name: str
    subject: Optional[str] = None
    body: str
    is_active: Optional[bool] = True


class EmailTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    is_active: Optional[bool] = None
