import uuid
import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import UUID, Column, String, DateTime, Boolean, Integer, Text
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
