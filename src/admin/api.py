import time
import logging
from dotenv import load_dotenv
from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from src.services.admin.service import admin_check, delete_auth_mail, new_admin, list_mail, new_auth, update_auth_mail
from src.utils.response import serialize_response

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter(
	prefix="/api",
	tags=["Payment-Process"],
	responses={
		400: {"description": "Bad Request"},
		404: {"description": "Not Found"},
		500: {"description": "Internal Server Error"},
	},
)

@router.post("/create_admin")
def create_admin(payload: Dict[str, Any]) :
    try:
        return new_admin(payload)
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.post("/admin/login")
def admin_login(email: str, password: str) :
    try:
        return admin_check(email, password)
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.get("/list_auth_mail")
def main() :
    try:
        return list_mail()
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.post("/create_auth_mail")
def new_auth_mail(payload: Dict[str, Any]) :
    try:
        return new_auth(payload)
    except ValueError as e:
        logger.warning("[create_admin] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })
    
@router.patch("/delete_auth_mail/")
def delete_auth(auth_mail_id: str):
    try:
        return delete_auth_mail(auth_mail_id)
    except ValueError as e:
        logger.warning("[delete_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })

@router.patch("/update_auth_mail/")
def update_auth(auth_mail_id: str, payload: Dict[str, Any]):
    try:
        return update_auth_mail(auth_mail_id, payload)
    except ValueError as e:
        logger.warning("[update_auth_mail] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": str(e),
            })