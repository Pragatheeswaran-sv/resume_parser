import os
import json
import logging
from dotenv import load_dotenv
from fastapi import APIRouter
from src.services.candidate.service import candidate_datails
# from src.resume_filter.schemas import ResumeFilterRequest
from typing import List, Dict, Any
from src.celery.celery_app import celery
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

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

@router.get('/candidate_info')
def candidate_info():
    """
        This api is use to
    """
    return candidate_datails()