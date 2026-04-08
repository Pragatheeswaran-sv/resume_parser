import logging
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from src.services.candidate.service import candidate_datails, CandidateServiceError

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

@router.get("/candidates")
def candidate_info(
    page: str = "1",
    sort_by: str = "None",
    sort_type: str = "None",
) -> List[Dict[str, Any]]:
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
    except CandidateServiceError as e:
        logger.warning("Candidate service error: %s", e.message)
        raise HTTPException(
            status_code=e.status_code,
            detail={"status": "error", "message": e.message},
        )
    except Exception as e:
        logger.error("Unexpected error in candidate_info: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to get candidate information",
            },
        )
