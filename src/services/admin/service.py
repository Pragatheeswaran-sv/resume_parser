
from typing import Any, Dict
import logging

import json


from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import UUID, func, cast
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, AiModel, AiModelConfig, AiModelversion, AuthMail
from fastapi import  status

load_dotenv()
logger = logging.getLogger(__name__)

db = SessionLocal()

def admin_check(email: str, password: str) -> Dict[str, Any]:
    try:
        
        if email == "" or password == "":
            raise ValueError("Email and password must be provided")

        admin = db.query(Admin).filter_by(email_address=email).first()
        if not admin:
            raise ValueError("Admin not found")
        
        # Simulate a successful login
        return {
            "status": status.HTTP_200_OK,
            "message": "Admin logged in successfully",
            "data": {
                # "admin_id": "some-uuid",
                "name": admin.name,
                "email_address": email
            }
        }
    except Exception as e:
        logger.warning("[admin_check] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))  
    finally:
        db.close()     
    
def new_admin(payload):
    try:
        email = payload.get("email")
        password = payload.get("password")
        name = payload.get("name")
        admin = db.query(Admin).filter_by(email_address=email).first()
        if admin:
            raise ValueError("Admin with this email already exists")
        
        new_admin = Admin(
            name=name,
            email_address=email,
            password=password
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Admin created successfully",
            "data": {
                "admin_id": str(new_admin.admin_id),
                "name": new_admin.name,
                # "email_address": new_admin.email_address
            }
        }
    except Exception as e:
        logger.warning("[new_admin] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    finally:
        db.close()

def list_mail():
    try:
        auth_mails = db.query(AuthMail).filter(AuthMail.is_active == True).all()
        if not auth_mails:
            raise ValueError("No auth mails found")
        return {
            "status": status.HTTP_200_OK,
            "message": "Auth mails retrieved successfully",
            "data": [
                {
                    "auth_mail_id": str(auth_mail.auth_mail_id),
                    "email_address": auth_mail.email_address,
                    "connect_with": auth_mail.connect_with
                }
                for auth_mail in auth_mails
            ]
        }

    except Exception as e:
        logger.warning("[mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    
def new_auth(payload) :
    try:
        
        # data = request.json()
        email_address = payload.get("email")
        password = payload.get("password") 
        connect_with = payload.get("connect_with", {})
        if not email_address or not password:
            raise ValueError("Email and password must be provided")
        
        auth_mail = db.query(AuthMail).filter_by(email_address=email_address).first()
        if auth_mail:
            raise ValueError("Auth mail with this email already exists")
        new_auth_mail = AuthMail(
            email_address= email_address,
            password= password,
            connect_with= connect_with
            )
        db.add(new_auth_mail)
        db.commit()
        db.refresh(new_auth_mail)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Auth mail created successfully",
            "data": {
                "auth_mail_id": str(new_auth_mail.auth_mail_id),
                "email_address": new_auth_mail.email_address,
                "connect_with": new_auth_mail.connect_with
            }
        }             
    except Exception as e:
        logger.warning("[new_auth] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    
def delete_auth_mail(auth_mail_id: str):
    try:
        auth_mail = db.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
        if not auth_mail:
            raise ValueError("Auth mail not found")
        auth_mail.is_active = False
        db.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "Auth mail deleted successfully"
        }
    except Exception as e:
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    
def update_auth_mail(auth_mail_id: str, payload):
    try:
        auth_mail = db.query(AuthMail).filter_by(auth_mail_id=auth_mail_id).first()
        email_address = payload.get("email") if payload.get("email") else auth_mail.email_address
        password = payload.get("password") if payload.get("password") else auth_mail.password
        connect_with = payload.get("connect_with") if payload.get("connect_with") else auth_mail.connect_with

        if not auth_mail:
            raise ValueError("Auth mail not found")
        update_auth = db.query(AuthMail).filter_by(email_address=email_address, password=password).first()
        if update_auth:
            raise ValueError("Auth mail with this email, password and connect_with already exists, nothing to update")
        auth_mail.email_address = email_address
        auth_mail.password = password
        auth_mail.connect_with = connect_with
        db.commit()
        return {
            "status": status.HTTP_200_OK,
            "message": "Auth mail updated successfully"
        }
    except Exception as e:
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    
def list_model():
    try:

        models = db.query(AiModel).filter(AiModel.is_active == True).all()
        if not models:
            raise ValueError("No models found")
        
        return {
            "status": status.HTTP_200_OK,
            "message": "Models retrieved successfully",
            "data": [
                {
                    "model_id": model.ai_model_id,
                    "model_name": model.model_name,
                }
                for model in models
            ]
        }
    except Exception as e:
        logger.warning("[list_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    
def create_model(payload):
    """Create a new AI model entry.

    Returns a standard response dict with ``status``, ``message``, and created model ``data``.
    Raises ``ValueError`` for invalid payload or duplicate model names.
    """
    try:
        model_name = (payload.get("model_name") or "").strip()

        if not model_name:
            raise ValueError("Model name must be provided")

        existing_model = (
            db.query(AiModel)
            .filter(AiModel.model_name == model_name, AiModel.is_active == True)
            .first()
        )
        if existing_model:
            raise ValueError("Model with this name already exists")

        new_model = AiModel(model_name=model_name)
        db.add(new_model)
        db.commit()
        db.refresh(new_model)

        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model created successfully",
            "data": {
                "model_id": str(new_model.ai_model_id),
                "model_name": new_model.model_name,
            },
        }
    except Exception as e:
        logger.warning("[create_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))

def model_version(model_id):
    try:
        id = str(model_id)
        # print(type())
        model = db.query(AiModel).filter_by(ai_model_id=id, is_active=True).all()
        if not model:
            raise ValueError("No model found for the given model ID")
        model_versions = db.query(AiModelversion).filter_by(ai_model_id=id, is_active=True).all()
        if not model_versions:
            raise ValueError("No model versions found for the given model ID")
        return {
            "status": status.HTTP_200_OK,
            "message": "Model versions retrieved successfully",
            "data": [
                {
                    "model_version_id": str(model_version.ai_model_version_id),
                    "version_name": model_version.version_name,
                }
                for model_version in model_versions
            ]
        }             
    except Exception as e:
        logger.warning("[model_version] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))

def new_model_version(model_id, payload):
    try:
        model_id = str(model_id)
        version_name = payload.get("version_name") if payload.get("version_name") else None
        
        model = db.query(AiModel).filter_by(ai_model_id=model_id, is_active=True).first()
        if not model:
            raise ValueError("No model found for the given model ID")
        
        if not version_name or version_name.strip() == "" or version_name == None:
            raise ValueError("Version name must be provided")
        
        # version_name = f"{model.model_name}_v{len(db.query(AiModelversion).filter_by(ai_model_id=model_id).all()) + 1}"
        new_version = AiModelversion(
            ai_model_id = model_id,
            version_name = version_name
        )
        db.add(new_version)
        db.commit()
        db.refresh(new_version)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model version created successfully",
            "data": {
                "model_version_id": str(new_version.ai_model_version_id),
                "version_name": new_version.version_name,
            }
        }             
    except Exception as e:
        logger.warning("[new_model_version] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))    

def model_config(payload, admin_id):
    try:
        
        model_version_id = payload.get("model_version_id") 
        ai_model_id = payload.get("model_id") 
        print(ai_model_id)
        apikey = payload.get("apikey") if payload.get("apikey") else None
        print(apikey)
        version = payload.get("version") if payload.get("version") else None
        print(version)
        max_tokens = payload.get("max_tokens") if payload.get("max_tokens") else None
        print(max_tokens)
        temperature = payload.get("temperature") if payload.get("temperature") else None
        print(temperature)
        if not admin_id:
            raise ValueError("Admin ID must be provided")
        
        model = db.query(AiModel).filter_by(ai_model_id=ai_model_id, is_active=True).first()
        if not model:
            raise ValueError("No model found for the given model ID")

        model_version = db.query(AiModelversion).filter_by(ai_model_version_id=model_version_id, is_active=True).first()
        if not model_version:
            raise ValueError("No model version found for the given model version ID")
        
        
        new_config = AiModelConfig(
            ai_model_version_id = model_version_id,
            ai_model_id = ai_model_id,
            admin_id = admin_id,
            apikey = apikey,
            version = version,
            max_tokens = max_tokens
        )
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        return {
            "status": status.HTTP_201_CREATED,
            "message": "Model config created successfully",
            "data": {
                "model_config_id": str(new_config.ai_model_config_id),
                "model_id": str(new_config.ai_model_id),
                "model_name" : model.model_name,
                "model_version_id": str(new_config.ai_model_version_id),
                "model_version_name": model_version.version_name,
                "admin_id": str(new_config.admin_id),
                "apikey": new_config.apikey,
                "max_tokens": new_config.max_tokens,
            }
        }             
    except Exception as e:
        logger.warning("[model_config] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))
    
def get_model(admin_id):
    try:
        if not admin_id:
            raise ValueError("Admin ID must be provided")

        model_config =( db.query(
            func.json_build_object(
                'model_config_id', AiModelConfig.ai_model_config_id,
                'model_id', AiModelConfig.ai_model_id,
                'model_name', AiModel.model_name,
                'model_version_id', AiModelConfig.ai_model_version_id,
                'model_version_name', AiModelversion.version_name,
                'admin_id', AiModelConfig.admin_id,
                'apikey', AiModelConfig.apikey,
                'max_tokens', AiModelConfig.max_tokens,
                'temparature', AiModelConfig.temparature,
            )
        )
        .select_from(AiModelConfig).
        join(AiModel, AiModel.ai_model_id == AiModelConfig.ai_model_id).
        join(AiModelversion, AiModelversion.ai_model_version_id == AiModelConfig.ai_model_version_id).
        filter(AiModelConfig.admin_id == admin_id, AiModelConfig.is_active == True).
        first())
        
        if not model_config:
            raise ValueError("No model config found for the given admin ID")
        
        return{
            "status": status.HTTP_200_OK,
            "message": "Model config retrieved successfully",
            "data": model_config[0] if model_config else None
        }             
    except Exception as e:
        logger.warning("[get_model] Error: %s", str(e), exc_info=True)
        raise ValueError(str(e))