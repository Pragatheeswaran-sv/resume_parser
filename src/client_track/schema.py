from pydantic import BaseModel, field_validator
from typing import List, Optional, Literal
from uuid import UUID

class RoundInsertRequest(BaseModel):
    # round_id: UUID
    round_name: str

class ClientInsertRequest(BaseModel):
    company_name : str
    contact_person : str
    location : str
    email_address : str
    phone_number : str

class ClientUpdateRequest(BaseModel):
    company_name : str | None = None
    contact_person : str | None = None
    location : str | None = None
    email_address : str | None = None
    phone_number : str | None = None

class InterviewInsertRequest(BaseModel):
    resume_id : str
    client_id : str
    experience : str
    status : str
    role : str

class InterviewStatusRequest(BaseModel):
    interview_id : str
    round_id : str
    round_no : str
    scheduled_date : str
    meeting_link : str 
    feedback : str | None = None
    status : str

class InterviewStatusUpdateRequest(BaseModel):
    scheduled_date : str | None = None
    meeting_link : str | None = None
    status : str | None = None
