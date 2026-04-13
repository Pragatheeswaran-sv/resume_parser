import uuid
from sqlalchemy import JSON, UUID, Column, ForeignKey, Integer, String, DateTime, Boolean, Text, Time
from sqlalchemy.orm import relationship
from db.connection import Base
import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.sql import func

def ist_now():
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)

class Admin(Base):
    __tablename__ = "admin"

    admin_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    name = Column(Text)
    email_address = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now, nullable=False)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class Users(Base):
    __tablename__ = "users"

    user_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    name = Column(String(255), nullable=True)
    email_address = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    imap_password = Column("password", String(255), nullable=True)
    connect_with = Column(String(255), nullable=True, default= "")
    is_blocked = Column(Boolean, default=False)
    extraction_enabled = Column(Boolean, default=True)
    last_extraction_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now, nullable=False)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class AiModel(Base):
    __tablename__ = "ai_models"

    ai_model_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    model_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now, nullable=False)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

class AiModelversion(Base):
    __tablename__ = "ai_model_version"

    ai_model_version_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    ai_model_id = Column(UUID(as_uuid=True), ForeignKey("ai_models.ai_model_id"), nullable = True)
    version_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now, nullable=False)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    ai_model = relationship("AiModel")

class AiModelConfig(Base):
    __tablename__ = "ai_model_configs"

    ai_model_config_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    ai_model_version_id = Column(UUID(as_uuid=True), ForeignKey("ai_model_version.ai_model_version_id"), nullable = True)
    ai_model_id = Column(UUID(as_uuid=True), ForeignKey("ai_models.ai_model_id"), nullable = True)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin.admin_id"), nullable = True)
    apikey = Column(String(255), nullable=True)
    version = Column(String(255), nullable=True)
    max_tokens = Column(Integer, nullable=True)
    temparature = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=False), default=ist_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now, nullable=False)
    created_by = Column(String, nullable = True)
    updated_by = Column(String, nullable = True)
    is_active = Column(Boolean, default = True)

    ai_model_version = relationship("AiModelversion")
    ai_model = relationship("AiModel")
    admin = relationship("Admin")


class ExtractionConfig(Base):
    """Singleton-style table: only one active row at a time."""
    __tablename__ = "extraction_config"

    config_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    is_paused = Column(Boolean, default=False)
    interval_minutes = Column(Integer, default=15)
    created_at = Column(DateTime(timezone=False), default=ist_now)
    updated_at = Column(DateTime(timezone=False), default=ist_now, onupdate=ist_now)
    is_active = Column(Boolean, default=True)

    window_enabled = Column(Boolean, default=False)
    window_start_time = Column(String(5), nullable=True)
    window_end_time = Column(String(5), nullable=True)
    window_timezone = Column(String(50), default="Asia/Kolkata")

    schedule_type = Column(String(10), default="hourly")
    weekday = Column(String(10), nullable=True)            
