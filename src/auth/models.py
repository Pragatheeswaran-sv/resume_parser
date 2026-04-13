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
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)
    
    source = relationship("OauthSource")


class RefreshToken(Base):
    """Stores issued refresh tokens for JWT rotation.

    Each row represents a single refresh token.  On rotation the old row is
    revoked (``is_revoked = True``) and a new row is created.  Logging out
    revokes the entire family via ``family_id``.
    """
    __tablename__ = "refresh_tokens"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    role = Column(String(10), nullable=False)
    family_id = Column(UUID, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=False), nullable=False)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)