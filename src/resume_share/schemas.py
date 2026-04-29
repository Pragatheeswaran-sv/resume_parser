from typing import List, Optional
from pydantic import BaseModel, EmailStr


class ShareResumeRequest(BaseModel):
    candidate_id: str
    resume_id: str
    to_address: EmailStr
    cc_address: Optional[List[EmailStr]] = None


class ShareResumeResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[str] = None
