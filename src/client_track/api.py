import logging
from src.client_track.schema import RoundInsertRequest
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Query, Depends
from src.services.client_track.service import add_round, delete_round, rounds, update_round
from src.admin.dependencies import get_current_user
from typing import List, Dict, Any
from src.services.candidate.service import candidate_datails, CandidateServiceError
from src.resume_filter.schemas import ResumeFilterRequest
from pydantic import ValidationError
from src.utils.response import serialize_response
from src.services.candidate.service import export_candidate
from src.services.resume_filter.service import (
    search_resumes
)

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter(
	prefix="/api",
	tags=["Candidates"],
	responses={
		400: {"description": "Bad Request"},
		404: {"description": "Not Found"},
		500: {"description": "Internal Server Error"},
	},
)

@router.get("/interview_round")
def interview_round(_user = get_current_user):
    try:
        return rounds()
    except Exception as e:
        logger.error(f"[Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.post("/add_new_round")
def create_interview_round(payload: RoundInsertRequest, _user =  Depends(get_current_user)):
    try:
        user_name = _user.name
        return add_round(payload.model_dump(), user_name)
    except Exception as e:
        logger.error(f"[Create Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/update_round")
def update_interview_round(payload: RoundInsertRequest, round_id, _user =  Depends(get_current_user)):
    try:
        user_name = _user.name
        return update_round(payload.model_dump(), round_id, user_name)
    except Exception as e:
        logger.error(f"[Update Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/delete_round")
def delete_interview_round(round_id, _user =  Depends(get_current_user)):
    try:
        user_name = _user.name
        return delete_round(round_id, user_name)
    except Exception as e:
        logger.error(f"[Delete Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )