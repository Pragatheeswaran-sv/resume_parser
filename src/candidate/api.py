import logging
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Dict, Any
from src.services.candidate.service import candidate_datails, CandidateServiceError
from src.resume_filter.schemas import ResumeFilterRequest, SemanticSearchRequest
from pydantic import ValidationError
from src.utils.response import serialize_response
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

# @router.get("/candidates")
# def candidate_info(
#     page: str = "1",
#     sort_by: str = "None",
#     sort_type: str = "None",
# ) -> List[Dict[str, Any]]:
#     """
#         Get Candidate Details

#         Retrieves complete candidate details by joining multiple related tables
#         such as Candidate, Education, WorkExperience, Skill, Resume, Company, CandidateSkills, CandidateSkills and Attachment data.

#         Returns:
#             list: A list of candidate detail objects containing structured profile information.

#         Response Includes:
#             - candidate_id
#             - personal details
#             - education details
#             - experience details
#             - skills
#             - resume information

#         Raises:
#             HTTPException: If candidate data retrieval fails.
#     """
#     try:
#         return candidate_datails(page, sort_by, sort_type)
#     except CandidateServiceError as e:
#         logger.warning("Candidate service error: %s", e.message)
#         raise HTTPException(
#             status_code=e.status_code,
#             detail={"status": "error", "message": e.message},
#         )
#     except Exception as e:
#         logger.error("Unexpected error in candidate_info: %s", str(e), exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail={
#                 "status": "error",
#                 "message": "Failed to get candidate information",
#             },
#         )
    

@router.post("/candidates")
def get_candidates(
    filters: Dict[str, Any] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Retrieve candidate information with optional filtering, sorting, and pagination.

    This unified endpoint serves two purposes:

    1. **Fetch All Candidates (Default Behavior)**
    - If no request body (filters) is provided, the API returns all active candidates.
    - Supports pagination via `page` and `page_size`.

    2. **Filter Candidates (Structured Filtering)**
    - If a JSON body is provided, candidates are filtered based on the given criteria.
    - Only structured database filtering is supported (semantic search is NOT included).

    Filtering Options:
        - name (str): Filter by candidate name (partial match)
        - file_name (str): Filter by resume file name
        - skills (List[str]): List of skill UUIDs
        - education (List[str]): List of education UUIDs
        - roles (List[str]): List of role UUIDs
        - companies (List[str]): List of company names
        - min_experience (float): Minimum years of experience
        - max_experience (float): Maximum years of experience
        - passout_start_year (int): Minimum graduation year
        - passout_end_year (int): Maximum graduation year
        - percentage (float): Minimum percentage
        - sort_by (str): Field to sort by (must be in allowed fields)
        - sort_order (str): Sorting order ('asc' or 'desc')

    Query Parameters:
        - page (int, default=1): Page number (must be >= 1)
        - page_size (int, default=20): Number of records per page (1–100)

    Request Body:
        - Optional JSON object containing filter criteria.
        - If empty or not provided, all candidates are returned.

    Returns:
        list[dict]: A list of candidate records, including:
            - candidate_id
            - name, email, phone_number, location
            - total_experience
            - education details
            - skills
            - work experience
            - (last element contains total_record count)
    """
    try:
        #1: No filters → behave like old /candidates
        if not filters:
            return candidate_datails(page, None, None)

        # Filters present → validate & filter
        try:
            parsed_filters = ResumeFilterRequest(**filters).model_dump()
        except ValidationError as ve:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Invalid filter parameters",
                    "errors": [
                        {
                            "field": ".".join(str(loc) for loc in err.get("loc", [])),
                            "message": err.get("msg", "")
                        }
                        for err in ve.errors()
                    ],
                },
            )

        parsed_filters["page"] = page
        parsed_filters["page_size"] = page_size

        rows = search_resumes(parsed_filters)

        return serialize_response(rows)

    except CandidateServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"status": "error", "message": e.message},
        )

    except Exception as e:
        logger.error("Error in unified candidates API: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Failed to fetch candidates"},
        )
