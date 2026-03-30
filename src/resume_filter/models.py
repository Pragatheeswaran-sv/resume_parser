# from tokenize import String
import datetime
import uuid
from sqlalchemy import UUID, Boolean, Column, DateTime, Integer, Text, Numeric, ARRAY, JSON, TIMESTAMP, ForeignKey,String
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from db.connection import Base
from src.email_reader.models import Attachment
from src.candidate.models import Candidate
from sqlalchemy.orm import relationship
from zoneinfo import ZoneInfo

def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))

class Resume(Base):
    __tablename__ = "resumes"

    resume_id = Column(UUID, primary_key=True, index=True, default= uuid.uuid4)
    embedding = Column(Vector(384))
    attachment_id = Column(UUID(as_uuid=True), ForeignKey("attachments.attachment_id"), nullable = True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable = True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)
    
    attachment = relationship("Attachment")
    candidate = relationship("Candidate")