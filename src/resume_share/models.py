import uuid
import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID, Column, ForeignKey, String, DateTime, Boolean, Integer, Text
from sqlalchemy.orm import relationship
from db.connection import Base


def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)


class EmailProviderConfig(Base):
    __tablename__ = "email_provider_config"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    provider_name = Column(String(50), nullable=False)
    from_email = Column(String(255), nullable=False)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    tls_enabled = Column(Boolean, default=True)
    active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    template_name = Column(String(255), nullable=False, unique=True)
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    is_active = Column(Boolean, default=True)

class EmailNotification(Base):
    __tablename__ = "email_notification"

    email_share_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    to_address = Column(String(255), nullable=False)
    cc_address = Column(String(255), nullable=True)
    # candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable=False) 
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.resume_id"), nullable=False)
    subject = Column(String(500), nullable=True)
    mail_body = Column(Text, nullable=True)
    status = Column(String, default='Pending')
    is_active = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    sent_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)

    # candidate = relationship("Candidate")
    resume = relationship("Resume")
