import logging
from src.client_track.schema import ClientInsertRequest, ClientUpdateRequest, InterviewInsertRequest, InterviewStatusRequest, InterviewStatusUpdateRequest, RoundInsertRequest
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Query, Depends
from src.services.client_track.service import add_client, add_interview, add_interview_status, add_round, delete_round, modify_client, modify_interview_status, remove_client, remove_interview, rounds, update_round, view_clients, view_interview_status, view_interviews
from src.admin.dependencies import get_current_admin_or_user
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


def get_current_user_or_admin_name(_current_role):
    role = _current_role.get('role')
    if role == 'user':
        data = _current_role.get('data')
        name = data.name
    else:
        data = _current_role.get('data')
        name = data.name
    return name


@router.get("/interview_round")
def interview_round(_current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return rounds()
    except Exception as e:
        logger.error(f"[Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.post("/add_new_round")
def create_interview_round(payload: RoundInsertRequest, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return add_round(payload.model_dump(), name)
    except Exception as e:
        logger.error(f"[Create Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/update_round")
def update_interview_round(payload: RoundInsertRequest, round_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return update_round(payload.model_dump(), round_id, name)
    except Exception as e:
        logger.error(f"[Update Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/delete_round")
def delete_interview_round(round_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return delete_round(round_id, name)
    except Exception as e:
        logger.error(f"[Delete Interview Round] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.get("/view_clients")
def get_client(page = 1, page_size = 10, filter_column = None, filter_by = None, sort_by = None, sort_order = None, _current_role = Depends(get_current_admin_or_user)):
    try:
        return view_clients(int(page), int(page_size), filter_column, filter_by, sort_by, sort_order)
    except Exception as e:
        logger.error(f"[View Client] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.post("/add_client")
def new_client(payload: ClientInsertRequest, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return add_client(payload.model_dump(), name)
    except Exception as e:
        logger.error(f"[Add Client] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/update_client")
def update_client(payload: ClientUpdateRequest, client_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return modify_client(payload.model_dump(), client_id, name)
    except Exception as e:
        logger.error(f"[Update Client] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/delete_client")
def delete_client(client_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return remove_client(client_id, name)
    except Exception as e:
        logger.error(f"[Delete Client] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.get("/view_interviews")
def get_interviews(page = 1, page_size = 10, filter_column = None, filter_by = None, sort_by = None, sort_order = None, _current_role = Depends(get_current_admin_or_user)):
    try:
        return view_interviews(int(page), int(page_size), filter_column, filter_by, sort_by, sort_order)
    except Exception as e:
        logger.error(f"[View Interviews] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
   
@router.post("/add_interview")
def new_interview(payload: InterviewInsertRequest, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return add_interview(payload.model_dump(), name)
    except Exception as e:
        logger.error(f"[Add Interviews] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.patch("/delete_interview")
def delete_interviw(interview_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return remove_interview(interview_id, name)
    except Exception as e:
        logger.error(f"[Delete interview] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
   
@router.get("/view_interview_status")
def get_interview_status(interview_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        return view_interview_status(interview_id)
    except Exception as e:
        logger.error(f"[View Interview Status] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
    
@router.post("/add_interview_status")
def interview_status(payload: InterviewStatusRequest, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return add_interview_status(payload.model_dump(), name)
    except Exception as e:
        logger.error(f"[Add Interviews] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )

@router.patch("/update_interview_status")
def update_interview_status(payload: InterviewStatusUpdateRequest, interview_status_id, _current_role = Depends(get_current_admin_or_user)):
    try:
        name = get_current_user_or_admin_name(_current_role)
        return modify_interview_status(payload.model_dump(), interview_status_id, name)
    except Exception as e:
        logger.error(f"[Update Interview Status] Error :{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": str(e)},
        )
   