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

@router.get('/candidates')
def candidate_info(page, sort_by, sort_type):
    """
        Get Candidate Details

        Retrieves complete candidate details by joining multiple related tables
        such as Candidate, Education, WorkExperience, Skill, Resume, Company, CandidateSkills, CandidateSkills and Attachment data.

        Returns:
            list: A list of candidate detail objects containing structured profile information.

        Response Includes:
            - candidate_id
            - personal details
            - education details
            - experience details
            - skills
            - resume information

        Raises:
            HTTPException: If candidate data retrieval fails.
    """
    try:
        return candidate_datails(page, sort_by, sort_type)
    except Exception as e:
        logger.error(f"ERROR in candidate: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to get candidate information",
                "error": str(e)
            }
        )

@router.get('/sort')
def sort_candidate(page, sort_by, sort_type):
    try:
        return sort(page, sort_by, sort_type)
    except Exception as e:
        logger.error(f"ERROR in candidate: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to get candidate information",
                "error": str(e)
            }
        )
