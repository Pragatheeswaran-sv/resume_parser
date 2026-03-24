import os
import json
import logging
from dotenv import load_dotenv
from fastapi import APIRouter
from src.services.resume_filter.service import process_resumes, search_resumes, semantic_search_resumes
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
    Filter or search resumes stored in the database.

    This endpoint supports two types of search:

    1. **Semantic Search**
       - If `query` is provided in the request body.
       - Uses embeddings with the `all-MiniLM-L6-v2` model.
       - Performs vector similarity search using PostgreSQL `pgvector`.

    2. **Structured Filter Search**
       - If `query` is NOT provided.
       - Filters resumes based on fields such as:
         - name
         - file_name
         - experience_min
         - experience_max
         - skills
         - companies
         - education

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
        "name": "John",
        "experience_min": 3,
        "skills": ["Python", "FastAPI"],
        "companies": ["Infosys"],
        "education": ["B.Tech"]
    }
    ```

    Returns:
        list[dict]: List of matching resumes.

    Example Response:
    ```json
    [
        {
            "id": 1,
            "file_name": "john_resume.pdf",
            "name": "John Doe",
            "total_experience": 5,
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "companies": ["Infosys"],
            "education": ["B.Tech Computer Science"]
        }
    ]
    ```
    """
    try:
        logger.info("this section executed")
        rows = []
        if 'query' in filters :
            query = filters.get("query")
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