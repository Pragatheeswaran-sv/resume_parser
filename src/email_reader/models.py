import uuid
from sqlalchemy import UUID, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from db.connection import Base
import datetime
from zoneinfo import ZoneInfo

def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))

class EmailVersion(Base):
    __tablename__ = "email_version"

    version_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    mailbox = Column(String)
    last_uid = Column(Integer)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class EmailLogs(Base):
    __tablename__ = "email_logs"

    email_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    message_id = Column(String)
    uid = Column(Integer)
    subject = Column(String)
    sender = Column(String)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class Attachment(Base):
    __tablename__ = "attachments"

    attachment_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("email_logs.email_id"))
    file_name = Column(String)
    is_resume = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    email = relationship("EmailLogs")