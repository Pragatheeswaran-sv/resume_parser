import uuid
from sqlalchemy import JSON, UUID, Column, ForeignKey, Integer, String, DateTime, Boolean, Text
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

class AuthMail(Base):
    __tablename__ = "auth_mail"

    auth_mail_id = Column(UUID, primary_key= True, default= uuid.uuid4)
    email_address = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    connect_with = Column(JSON, nullable=True)
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


                                                                                                                                 