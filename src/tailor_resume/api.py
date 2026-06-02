import time
import logging
from dotenv import load_dotenv
from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from src.services.tailor_resume.service import alter_resume
from src.services.resume_filter.service import (
    search_resumes, get_master_data,
    extract_filters_from_query, resolve_dynamic_filters, merge_filters, apply_filters
)
from src.services.nl_search.service import _execute_search, _load_search_session, nl_search_initial, nl_search_paginate
from src.resume_filter.schemas import (
    ResumeFilterRequest, DynamicFilterRequest, DynamicFilterResponse,
    NLSearchRequest, NLSearchPaginateRequest, NLSearchResponse,
)
from src.utils.response import serialize_response

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter(
	prefix="/api",
	tags=["Resume-Filter"],
	responses={
		400: {"description": "Bad Request"},
		404: {"description": "Not Found"},
		500: {"description": "Internal Server Error"},
	},
)

@router.post("/modify_resume")
def modify_resume(payload: Dict, resume_id: str):
    try:
        return alter_resume(payload, resume_id)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			content={"message": "An error occurred while modifying the resume.", "details": str(e)},
		)