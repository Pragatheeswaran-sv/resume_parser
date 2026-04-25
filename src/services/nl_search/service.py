"""Natural-language candidate search service.

Orchestrates:
1. LLM-based filter extraction  (reuses ``extract_filters_from_query``)
2. Dynamic-filter resolution     (reuses ``resolve_dynamic_filters``)
3. Redis-backed search-session caching
4. Paginated search execution    (reuses ``search_resumes``)
"""

import json
import uuid
import logging
import datetime as dt

from src.services.redis_client import get_redis, NL_SEARCH_TTL
from src.services.resume_filter.service import (
    extract_filters_from_query,
    resolve_dynamic_filters,
    search_resumes,
)
from src.resume_filter.schemas import (
    ResumeFilterRequest,
    DynamicFilterResponse,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "search:"


def _build_redis_key(search_id: str) -> str:
    return f"{REDIS_KEY_PREFIX}{search_id}"


def _store_search_session(
    search_id: str,
    raw_filters: dict,
    resolved_filters: dict,
    user_query: str,
) -> None:
    """Persist extracted + resolved filters in Redis with a configurable TTL."""
    r = get_redis()
    payload = {
        "filters": resolved_filters,
        "raw_filters": raw_filters,
        "user_query": user_query,
        "created_at": dt.datetime.utcnow().isoformat(),
    }
    r.setex(_build_redis_key(search_id), NL_SEARCH_TTL, json.dumps(payload))
    logger.info(
        "[nl_search] Stored session %s (TTL=%ds, filter_keys=%s)",
        search_id, NL_SEARCH_TTL, list(resolved_filters.keys()),
    )


def _load_search_session(search_id: str) -> dict | None:
    """Retrieve a previously cached search session, or ``None`` if expired / missing."""
    r = get_redis()
    raw = r.get(_build_redis_key(search_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("[nl_search] Corrupt cache entry for %s", search_id)
        return None


def _extract_and_resolve(user_query: str) -> tuple[dict, dict]:
    """Run the LLM extraction → UUID resolution pipeline.

    Returns ``(raw_filters, resolved_filters)`` where:
    * ``raw_filters``  – human-readable LLM output (for display in the response)
    * ``resolved_filters`` – UUID-resolved dict ready for ``search_resumes``
    """
    raw_filters = extract_filters_from_query(user_query)
    logger.info("[nl_search] LLM raw output: %s", raw_filters)

    if not raw_filters:
        raise ValueError("LLM could not extract any filters from the query")

    try:
        DynamicFilterResponse(**raw_filters)
    except ValidationError:
        pass

    resolved = resolve_dynamic_filters(raw_filters)
    logger.info("[nl_search] Resolved filters: %s", resolved)

    if not resolved:
        raise ValueError(
            "None of the LLM-extracted filter values matched known data. "
            "Extracted: " + ", ".join(f"{k}={v}" for k, v in raw_filters.items())
        )

    return raw_filters, resolved


def _execute_search(
    resolved_filters: dict,
    page: int,
    page_size: int,
    sort_by: str | None,
    sort_order: str,
    export: bool = False,
) -> tuple[list, int]:
    """Validate, inject pagination, and delegate to the existing ``search_resumes``."""
    filter_dict = dict(resolved_filters)
    filter_dict["page"] = page
    filter_dict["page_size"] = page_size
    if sort_by:
        filter_dict["sort_by"] = sort_by
    filter_dict["sort_order"] = sort_order

    try:
        parsed = ResumeFilterRequest(**filter_dict).model_dump()
    except ValidationError:
        parsed = filter_dict
    parsed["page"] = page
    parsed["page_size"] = page_size

    rows = search_resumes(parsed, export)
    total_record = 0
    candidates = []
    if rows:
        for item in rows:
            if isinstance(item, dict) and "total_record" in item:
                total_record = item["total_record"]
            else:
                candidates.append(item)

    return candidates, total_record


# ---- public API ----------------------------------------------------------

def nl_search_initial(
    user_query: str,
    page: int | None = 1,
    page_size: int | None = 20,
    sort_by: str | None = None,
    sort_order: str | None = "asc",
    export: bool = False,
) -> dict:
    """First-time NL search: LLM → resolve → cache → query → respond."""
    _page = page or 1
    _page_size = page_size or 20
    _sort_order = sort_order or "asc"

    raw_filters, resolved_filters = _extract_and_resolve(user_query)

    search_id = uuid.uuid4().hex
    _store_search_session(search_id, raw_filters, resolved_filters, user_query)

    candidates, total_record = _execute_search(
        resolved_filters, _page, _page_size, sort_by, _sort_order, export
    )

    return {
        "status": "success",
        "search_id": search_id,
        "user_query": user_query,
        "filters_applied": raw_filters,
        "candidates": candidates,
        "total_record": total_record,
        "page": _page,
        "page_size": _page_size,
    }


def nl_search_paginate(
    search_id: str,
    page: int | None = 1,
    page_size: int | None = 20,
    sort_by: str | None = None,
    sort_order: str | None = "asc",
    export: bool = False,
) -> dict:
    """Follow-up request: load cached filters → query → respond (no LLM call)."""
    _page = page or 1
    _page_size = page_size or 20
    _sort_order = sort_order or "asc"

    session = _load_search_session(search_id)
    if session is None:
        raise LookupError(
            f"search_id '{search_id}' not found or expired. "
            "Please start a new search."
        )

    resolved_filters = session["filters"]
    raw_filters = session.get("raw_filters", resolved_filters)
    user_query = session.get("user_query")

    candidates, total_record = _execute_search(
        resolved_filters, _page, _page_size, sort_by, _sort_order, export
    )

    return {
        "status": "success",
        "search_id": search_id,
        "user_query": user_query,
        "filters_applied": raw_filters,
        "candidates": candidates,
        "total_record": total_record,
        "page": _page,
        "page_size": _page_size,
    }
