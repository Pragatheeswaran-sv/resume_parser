import uuid
from sqlalchemy import UUID, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from db.connection import Base
import datetime
from zoneinfo import ZoneInfo

def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))

class OauthSource(Base):
    __tablename__ = "oauth_source"

    source_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    source_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class OauthCredentials(Base):
    __tablename__ = "oauth_credentials"

    credential_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    email = Column(String)
    access_token = Column(String)
    refresh_token = Column(String)
    expires_in = Column(Integer)
    source_id = Column(UUID(as_uuid=True), ForeignKey("oauth_source.source_id"), nullable = True)
    api_domain = Column(String, nullable = True)
    last_uid = Column(Integer)
    last_processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)
    
    source = relationship("OauthSource")