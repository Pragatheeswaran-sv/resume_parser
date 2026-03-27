import os
import json
import logging
from dotenv import load_dotenv
from fastapi import APIRouter
from src.services.resume_filter.service import process_resumes, search_resumes, semantic_search_resumes, get_master_data
from src.resume_filter.schemas import ResumeFilterRequest
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

@router.post("/filter_resumes")
def filter_resumes(filters: dict)-> List[Dict[str, Any]]:
    """
    Filter or search resumes stored in the database with pagination support.

    This endpoint supports two types of search:

    1. **Semantic Search**
       - If `query` is provided in the request body.
       - Uses embeddings with the `all-MiniLM-L6-v2` model.
       - Performs vector similarity search using PostgreSQL `pgvector`.

    2. **Structured Filter Search**
       - If `query` is NOT provided.
       - Filters resumes based on fields such as:
         - skills (UUID list)
         - education (UUID list)
         - roles (UUID list)
         - min_experience / max_experience
         - passout_start_year / passout_end_year
         - percentage
         - companies
         - name
         - file_name

    Query Parameters:
        - page (int, default=1): Page number for pagination
        - page_size (int, default=20): Number of records per page

    Request Body Examples:

    **Semantic Search**
    ```json
    {
        "query": "Python developer with FastAPI experience",
        "limit": 3
    }
    ```

    **Structured Filter Search**
    ```json
    {
        "skills": ["uuid", "uuid"],
        "education": ["uuid"],
        "roles": ["uuid"],
        "min_experience": "3",
        "max_experience": "5",
        "passout_start_year": "2020",
        "passout_end_year": "2023",
        "percentage": "80",
        "sort_by": "total_experience",
        "sort_order": "desc"
    }
    ```

    Returns:
        list[dict]: List of matching candidate resumes with pagination info.

    Example Response:
    ```json
    [
        {
            "candidate_id": "uuid",
            "name": "John Doe",
            "email": "john@example.com",
            "phone_number": "1234567890",
            "location": "New York",
            "total_experience": 5,
            "education": [
                {
                    "education_id": "uuid",
                    "education": "B.Tech",
                    "institution": "MIT",
                    "percentage": 8.5,
                    "year_of_passed": 2020
                }
            ],
            "skills": [
                {
                    "skill_id": "uuid",
                    "skill": "Python"
                }
            ],
            "work_experience": [
                {
                    "role_id": "uuid",
                    "role": "Senior Developer",
                    "company_name": "TechCorp",
                    "company_location": "New York",
                    "start_date": "2020-01-15",
                    "end_date": null,
                    "is_present": true
                }
            ]
        },
        {
            "total_record": 150
        }
    ]
    ```
    """
    try:
        logger.info("this section executed")
        rows = []
        if 'query' in filters :
            query = filters.get("query")
            if not query:
                raise HTTPException(status_code=400, detail="Query cannot be empty")
            top_k = filters.get("limit", 1)
            rows = semantic_search_resumes(query, top_k)
        else:
            filters = ResumeFilterRequest()
            filters = filters.model_dump()
            logger.info(f"this if section executed{filters}")
            rows = search_resumes(filters)
            logger.info(f'Rows----> {rows}')
        logger.info(f"NAV---> the source {rows}")
        result = [
            {
                "id": r.id,
                "file_name": r.file_name,
                "name": r.name,
                "total_experience": float(r.total_experience),
                "skills": r.skills,
                "companies": r.companies,
                "education": r.education,
            }
            for r in rows
        ]

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "count": len(result),
                "data": result
            }
        )

    except Exception as e:
        logger.error(f"ERROR in filter_resumes: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to filter resumes",
                "error": str(e)
            }
        )

@router.post("/semantic_search")
def semantic_search(body: dict):
    query = body.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    top_k = body.get("top_k", 1)
    results = semantic_search_resumes(query, top_k)

    return [
        {
            "id": r.id,
            "name": r.name,
            "file_name": r.file_name,
            "experience": float(r.total_experience),
            "skills": r.skills
        }
        for r in results
    ]

@router.get("/show_filter")
def show_filter():
    """
    Fetch master data for filters: Roles, Education, Skills.
    
    This endpoint is called during initial page render to populate filter options.
    
    Returns:
        JSON: Master data in structured format.
    
    Example Response:
    ```json
    {
        "status": "success",
        "data": {
            "roles": [
                {"id": "uuid", "name": "Software Engineer"}
            ],
            "education": [
                {"id": "uuid", "name": "B.Tech"}
            ],
            "skills": [
                {"id": "uuid", "name": "Python"}
            ]
        }
    }
    ```
    """
    try:
        data = get_master_data()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "data": data
            }
        )
    except Exception as e:
        logger.error(f"ERROR in show_filter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to fetch master data",
                "error": str(e)
            }
        )