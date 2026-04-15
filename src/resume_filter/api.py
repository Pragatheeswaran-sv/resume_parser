"""Resume filter REST API router.

Provides endpoints for structured filter search, semantic (vector)
search, and master-data retrieval for filter dropdowns.
"""

import time
import logging
from dotenv import load_dotenv
from pydantic import ValidationError
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from src.services.resume_filter.service import (
    search_resumes, semantic_search_resumes, get_master_data,
    extract_filters_from_query, resolve_dynamic_filters, merge_filters,
)
from src.services.nl_search.service import nl_search_initial, nl_search_paginate
from src.resume_filter.schemas import (
    ResumeFilterRequest, SemanticSearchRequest, DynamicFilterRequest, DynamicFilterResponse,
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

@router.post("/generate_dynamic_filters")
def generate_dynamic_filters(body: dict) -> Dict[str, Any]:
    """Generate structured filter payload from a natural-language recruiter query.

    The frontend should persist the returned ``dynamic_filters`` in
    localStorage and send them alongside standard UI filters on every
    subsequent request to ``/filter_resumes``.
    """
    start_time = time.time()
    logger.info("[generate_dynamic_filters] Request received | body_keys=%s", list(body.keys()) if body else "empty")

    query = (body or {}).get("query", "")
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "A non-empty 'query' string is required"},
        )

    try:
        req = DynamicFilterRequest(query=query)
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Invalid request",
                "errors": [
                    {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "")}
                    for err in ve.errors()
                ],
            },
        )

    try:
        raw_filters = extract_filters_from_query(req.query)
        logger.info("[generate_dynamic_filters] LLM extracted: %s", raw_filters)

        try:
            validated = DynamicFilterResponse(**raw_filters).model_dump(exclude_none=True)
        except ValidationError:
            validated = raw_filters

        elapsed = round(time.time() - start_time, 3)
        logger.info("[generate_dynamic_filters] Completed in %ss", elapsed)
        return {"status": "success", "data": validated}

    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        logger.error("[generate_dynamic_filters] Error after %ss: %s", elapsed, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to generate dynamic filters"},
        )


@router.post("/filter_resumes")
def filter_resumes(
    filters: dict,
    page: int = Query(default=1, ge=1, description="Page number (must be >= 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Results per page (1-100)")
) -> List[Dict[str, Any]]:
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
    start_time = time.time()
    logger.info(
        "[filter_resumes] Request received | page=%s, page_size=%s, payload_keys=%s",
        page, page_size, list(filters.keys()) if filters else "empty"
    )

    if not filters or not isinstance(filters, dict):
        logger.warning("[filter_resumes] Empty or invalid request body received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a non-empty JSON object"
        )

    try:
        rows = []

        is_semantic = "query" in filters and filters.get("query")
        is_combined = "filters" in filters or "dynamic_filters" in filters

        if is_semantic:
            logger.info("[filter_resumes] Semantic search mode detected")
            try:
                semantic_req = SemanticSearchRequest(
                    query=filters["query"],
                    top_k=filters.get("limit", filters.get("top_k", 5))
                )
            except ValidationError as ve:
                logger.warning(
                    "[filter_resumes] Semantic search validation failed: %s", ve.errors()
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Invalid semantic search parameters",
                        "errors": [
                            {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "")}
                            for err in ve.errors()
                        ],
                    }
                )

            logger.info(
                "[filter_resumes] Executing semantic search | query='%s', top_k=%s",
                semantic_req.query[:50], semantic_req.top_k
            )
            rows = semantic_search_resumes(semantic_req.query, semantic_req.top_k or 5)
            logger.info(
                "[filter_resumes] Semantic search returned %s results",
                len(rows) if rows else 0
            )

        elif is_combined:
            logger.info("[filter_resumes] Combined filter mode detected (standard + dynamic)")
            standard_raw = filters.get("filters") or {}
            dynamic_raw = filters.get("dynamic_filters") or {}

            resolved_dynamic = resolve_dynamic_filters(dynamic_raw) if dynamic_raw else {}
            logger.info("[filter_resumes] Resolved dynamic filters: %s", resolved_dynamic)

            merged = merge_filters(standard_raw, resolved_dynamic)

            try:
                parsed_filters = ResumeFilterRequest(**merged).model_dump()
            except ValidationError as ve:
                logger.warning("[filter_resumes] Merged filter validation failed: %s", ve.errors())
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Invalid filter parameters",
                        "errors": [
                            {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "")}
                            for err in ve.errors()
                        ],
                    },
                )

            parsed_filters["page"] = page
            parsed_filters["page_size"] = page_size

            active_filters = {
                k: v for k, v in parsed_filters.items()
                if v is not None and k not in ("action_type", "page", "page_size")
            }
            logger.info(
                "[filter_resumes] Merged active_filters=%s, page=%s, page_size=%s",
                active_filters, page, page_size,
            )

            rows = search_resumes(parsed_filters)
            result_count = len(rows) - 1 if rows else 0
            logger.info("[filter_resumes] Combined search returned %s results", result_count)

        else:
            logger.info("[filter_resumes] Structured filter mode detected")
            try:
                parsed_filters = ResumeFilterRequest(**filters).model_dump()
            except ValidationError as ve:
                logger.warning(
                    "[filter_resumes] Filter validation failed: %s", ve.errors()
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Invalid filter parameters",
                        "errors": [
                            {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "")}
                            for err in ve.errors()
                        ],
                    }
                )

            parsed_filters["page"] = page
            parsed_filters["page_size"] = page_size

            active_filters = {
                k: v for k, v in parsed_filters.items()
                if v is not None and k not in ("action_type", "page", "page_size")
            }
            logger.info(
                "[filter_resumes] Validated filters | active_filters=%s, page=%s, page_size=%s",
                active_filters, page, page_size
            )

            rows = search_resumes(parsed_filters)
            result_count = len(rows) - 1 if rows else 0
            logger.info("[filter_resumes] Structured search returned %s results", result_count)

        elapsed = round(time.time() - start_time, 3)
        logger.info("[filter_resumes] Request completed in %ss", elapsed)
        return serialize_response(rows)

    except HTTPException:
        raise

    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        logger.error(
            "[filter_resumes] Unexpected error after %ss: %s", elapsed, str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to filter resumes",
            }
        )

@router.post("/nl_search", response_model=NLSearchResponse)
def nl_search(body: dict) -> Dict[str, Any]:
    """Search candidates using a natural-language query.

    **First request** — provide ``user_query`` (and optional pagination/sort):
    the LLM extracts structured filters, results are returned, and a
    ``search_id`` is cached in Redis so that subsequent pages can be
    fetched without calling the LLM again.

    **Follow-up requests** — provide ``search_id`` (and pagination/sort)
    to page through the same result set.

    Request body (initial):
    ```json
    {
        "user_query": "Python developers with 3+ years of experience",
        "page": 1,
        "page_size": 20,
        "sort_by": "total_experience",
        "sort_order": "desc"
    }
    ```

    Request body (paginate):
    ```json
    {
        "search_id": "<hex id from first response>",
        "page": 2,
        "page_size": 20
    }
    ```
    """
    start_time = time.time()
    logger.info("[nl_search] Request received | keys=%s", list(body.keys()) if body else "empty")

    if not body or not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Request body must be a non-empty JSON object"},
        )

    search_id = body.get("search_id")

    try:
        if search_id:
            req = NLSearchPaginateRequest(**body)
            result = nl_search_paginate(
                search_id=req.search_id,
                page=req.page,
                page_size=req.page_size,
                sort_by=req.sort_by,
                sort_order=req.sort_order,
            )
        else:
            if not body.get("user_query"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Either 'user_query' or 'search_id' is required",
                    },
                )
            req = NLSearchRequest(**body)
            result = nl_search_initial(
                user_query=req.user_query,
                page=req.page,
                page_size=req.page_size,
                sort_by=req.sort_by,
                sort_order=req.sort_order,
            )

        result["candidates"] = serialize_response(result.get("candidates", []))
        elapsed = round(time.time() - start_time, 3)
        logger.info("[nl_search] Completed in %ss | search_id=%s", elapsed, result.get("search_id"))
        return result

    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Invalid request parameters",
                "errors": [
                    {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "")}
                    for err in ve.errors()
                ],
            },
        )

    except LookupError as le:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": str(le)},
        )

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": str(ve)},
        )

    except HTTPException:
        raise

    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        logger.error("[nl_search] Unexpected error after %ss: %s", elapsed, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Natural language search failed"},
        )


@router.post("/semantic_search")
def semantic_search(body: SemanticSearchRequest) -> List[Dict[str, Any]]:
    """Perform a standalone semantic (vector-similarity) search over resumes.

    Accepts a validated ``SemanticSearchRequest`` with a natural-language
    query and an optional ``top_k`` limit.  Returns matching candidates
    ranked by embedding similarity.
    """
    try:
        results = semantic_search_resumes(body.query, body.top_k or 5)
    except Exception as e:
        logger.error("[semantic_search] Error: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Semantic search failed"},
        )

    return results

@router.get("/filter_options")
def show_filter() -> Dict[str, Any]:
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
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error("ERROR in show_filter: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to fetch master data",
            }
        )
