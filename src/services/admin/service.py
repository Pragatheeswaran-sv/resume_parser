
from typing import Any, Dict
import logging


from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, AuthMail
from fastapi import  status

load_dotenv()
logger = logging.getLogger(__name__)

db = SessionLocal()

def admin_check(email: str, password: str) -> Dict[str, Any]:
    try:
        # Placeholder for actual authentication logic
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
        # Placeholder for actual logic to create auth mail
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