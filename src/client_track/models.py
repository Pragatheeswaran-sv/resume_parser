import uuid
from sqlalchemy import UUID, Column, Float, Integer, String, DateTime, ForeignKey, Boolean, Text, Date, JSON
from sqlalchemy.orm import relationship
from db.connection import Base
import datetime
from zoneinfo import ZoneInfo

def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))

class Clients(Base):
    __tablename__ = "clients"

    client_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    company_name = Column(String(255))
    contact_person = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    email_address = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class CandidateInterviews(Base):
    __tablename__ = 'candidate_interviews'

    interview_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.resume_id"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id"), nullable=False)
    experience = Column(String(5), nullable = True)
    status = Column(String(20), nullable = False, default= 'resume shared')
    role = Column(String(20), nullable = True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    resume = relationship("Resume")
    client = relationship("Clients")

class InterviewRounds(Base):
    __tablename__ = 'interview_rounds'

    round_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    round_name = Column(String(50), nullable = False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)


class InterviewStatus(Base):
    __tablename__ = 'interview_status'

    interview_round_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("candidate_interviews.interview_id"), nullable=False)
    round_id = Column(UUID(as_uuid=True), ForeignKey("interview_rounds.round_id"), nullable=False)
    round_no  = Column(String(5), nullable = False)
    scheduled_date = Column(DateTime(timezone=False), nullable=True)
    meeting_link = Column(String(255), nullable=False)
    feedback = Column(Text, nullable=False)
    status  = Column(Text, nullable=False, default='scheduled')
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    interview = relationship("CandidateInterviews")
    interview = relationship("InterviewRounds")