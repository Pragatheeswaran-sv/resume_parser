import os
import json
import logging
from dotenv import load_dotenv
from fastapi import APIRouter
from services.resume_filter.service import process_resumes, search_resumes, semantic_search_resumes
from resume_filter.schemas import ResumeFilterRequest

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

@router.post("/resume_track")
async def health_check():
    os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
    folder = "Resumes"

    data = process_resumes(folder)

    print("\nExtracted Data:\n")
    return json.dumps(data, indent=2)


@router.post("/filter_resumes")
def filter_resumes(filters: dict):
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
    return [
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