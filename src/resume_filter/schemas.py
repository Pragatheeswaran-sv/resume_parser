import re
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Any, Dict, List, Optional


ALLOWED_SORT_FIELDS = {"name", "total_experience", "created_at", "updated_at", "location", "year_of_passed", "email", "percentage"}
ALLOWED_SORT_ORDERS = {"asc", "desc"}
MAX_PAGE_SIZE = 100
MIN_YEAR = 1950
MAX_YEAR = 2100


# class ResumeFilterRequest(BaseModel):
#     action_type: str = "filter"
#     name: Optional[str] = None
#     file_name: Optional[str] = None
#     min_experience: Optional[float] = None
#     max_experience: Optional[float] = None
#     skills: Optional[List[str]] = None
#     education: Optional[List[str]] = None
#     roles: Optional[List[str]] = None
#     companies: Optional[List[str]] = None
#     passout_start_year: Optional[int] = None
#     passout_end_year: Optional[int] = None
#     percentage: Optional[float] = None
#     page: Optional[int] = 1
#     page_size: Optional[int] = 20
#     sort_by: Optional[str] = None
#     sort_order: Optional[str] = "asc"

#     @field_validator("skills", "education", "roles", mode="before")
#     @classmethod
#     def validate_uuid_lists(cls, v, info):
#         if v is None:
#             return v
#         if not isinstance(v, list):
#             raise ValueError(f"{info.field_name} must be a list of UUID strings")
#         validated: list[str] = []
#         for idx, item in enumerate(v):
#             try:
#                 validated.append(str(UUID(str(item))))
#             except (ValueError, AttributeError):
#                 raise ValueError(
#                     f"{info.field_name}[{idx}] = '{item}' is not a valid UUID"
#                 )
#         return validated

#     @field_validator("min_experience", "max_experience", mode="before")
#     @classmethod
#     def validate_experience(cls, v, info):
#         if v is None or v == "":
#             return None
#         try:
#             val = float(v)
#         except (ValueError, TypeError):
#             raise ValueError(f"{info.field_name} must be a valid number, got '{v}'")
#         if val < 0:
#             raise ValueError(f"{info.field_name} cannot be negative")
#         if val > 50:
#             raise ValueError(f"{info.field_name} cannot exceed 50 years")
#         return val

#     @field_validator("percentage", mode="before")
#     @classmethod
#     def validate_percentage(cls, v):
#         if v is None or v == "":
#             return None
#         try:
#             val = float(v)
#         except (ValueError, TypeError):
#             raise ValueError(f"percentage must be a valid number, got '{v}'")
#         if val < 0 or val > 100:
#             raise ValueError("percentage must be between 0 and 100")
#         return val

#     @field_validator("passout_start_year", "passout_end_year", mode="before")
#     @classmethod
#     def validate_passout_year(cls, v, info):
#         if v is None or v == "":
#             return None
#         try:
#             val = int(v)
#         except (ValueError, TypeError):
#             raise ValueError(f"{info.field_name} must be a valid integer year, got '{v}'")
#         if val < MIN_YEAR or val > MAX_YEAR:
#             raise ValueError(f"{info.field_name} must be between {MIN_YEAR} and {MAX_YEAR}")
#         return val

#     @field_validator("page", mode="before")
#     @classmethod
#     def validate_page(cls, v):
#         if v is None:
#             return 1
#         try:
#             val = int(v)
#         except (ValueError, TypeError):
#             raise ValueError(f"page must be a positive integer, got '{v}'")
#         if val < 1:
#             raise ValueError("page must be >= 1")
#         return val

#     @field_validator("page_size", mode="before")
#     @classmethod
#     def validate_page_size(cls, v):
#         if v is None:
#             return 20
#         try:
#             val = int(v)
#         except (ValueError, TypeError):
#             raise ValueError(f"page_size must be a positive integer, got '{v}'")
#         if val < 1:
#             raise ValueError("page_size must be >= 1")
#         if val > MAX_PAGE_SIZE:
#             raise ValueError(f"page_size cannot exceed {MAX_PAGE_SIZE}")
#         return val

#     @field_validator("sort_by", mode="before")
#     @classmethod
#     def validate_sort_by(cls, v):
#         if v is None or v == "":
#             return None
#         if v not in ALLOWED_SORT_FIELDS:
#             raise ValueError(
#                 f"sort_by must be one of {ALLOWED_SORT_FIELDS}, got '{v}'"
#             )
#         return v

#     @field_validator("sort_order", mode="before")
#     @classmethod
#     def validate_sort_order(cls, v):
#         if v is None or v == "":
#             return "asc"
#         v_lower = str(v).lower()
#         if v_lower not in ALLOWED_SORT_ORDERS:
#             raise ValueError(
#                 f"sort_order must be 'asc' or 'desc', got '{v}'"
#             )
#         return v_lower

#     @field_validator("companies", mode="before")
#     @classmethod
#     def validate_companies(cls, v):
#         if v is None:
#             return v
#         if not isinstance(v, list):
#             raise ValueError("companies must be a list of strings")
#         for idx, item in enumerate(v):
#             if not isinstance(item, str) or not item.strip():
#                 raise ValueError(f"companies[{idx}] must be a non-empty string")
#         return [item.strip() for item in v]

#     @field_validator("name", "file_name", mode="before")
#     @classmethod
#     def validate_string_fields(cls, v, info):
#         if v is None:
#             return v
#         if not isinstance(v, str):
#             raise ValueError(f"{info.field_name} must be a string")
#         cleaned = v.strip()
#         if len(cleaned) > 255:
#             raise ValueError(f"{info.field_name} must not exceed 255 characters")
#         return cleaned if cleaned else None

#     @model_validator(mode="after")
#     def validate_experience_range(self):
#         if self.min_experience is not None and self.max_experience is not None:
#             if self.min_experience > self.max_experience:
#                 raise ValueError(
#                     f"min_experience ({self.min_experience}) cannot be greater "
#                     f"than max_experience ({self.max_experience})"
#                 )
#         return self

#     @model_validator(mode="after")
#     def validate_passout_year_range(self):
#         if self.passout_start_year is not None and self.passout_end_year is not None:
#             if self.passout_start_year > self.passout_end_year:
#                 raise ValueError(
#                     f"passout_start_year ({self.passout_start_year}) cannot be "
#                     f"greater than passout_end_year ({self.passout_end_year})"
#                 )
#         return self

class ResumeFilterRequest(BaseModel):
    action_type: str = "filter"
    name: Optional[List[str]] = None
    file_name: Optional[str] = None
    min_experience: Optional[float] = None
    max_experience: Optional[float] = None
    skills: Optional[List[str]] = None
    education: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    passout_start_year: Optional[int] = None
    passout_end_year: Optional[int] = None
    percentage: Optional[float] = None
    page: Optional[int] = 1
    page_size: Optional[int] = 20
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"

    @field_validator("skills", "education", "roles", mode="before")
    @classmethod
    def validate_list_of_str_or_uuid(cls, v, info):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list")
        validated: list[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"{info.field_name}[{idx}] must be a non-empty string"
                )
            item = item.strip()
            try:
                validated.append(str(UUID(item)))
            except ValueError:
                validated.append(item)
        return validated

    @field_validator("min_experience", "max_experience", mode="before")
    @classmethod
    def validate_experience(cls, v, info):
        if v is None or v == "":
            return None
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"{info.field_name} must be a valid number, got '{v}'")
        if val < 0:
            raise ValueError(f"{info.field_name} cannot be negative")
        if val > 50:
            raise ValueError(f"{info.field_name} cannot exceed 50 years")
        return val

    @field_validator("percentage", mode="before")
    @classmethod
    def validate_percentage(cls, v):
        if v is None or v == "":
            return None
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"percentage must be a valid number, got '{v}'")
        if val < 0 or val > 100:
            raise ValueError("percentage must be between 0 and 100")
        return val

    @field_validator("passout_start_year", "passout_end_year", mode="before")
    @classmethod
    def validate_passout_year(cls, v, info):
        if v is None or v == "":
            return None
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"{info.field_name} must be a valid integer year, got '{v}'")
        if val < MIN_YEAR or val > MAX_YEAR:
            raise ValueError(f"{info.field_name} must be between {MIN_YEAR} and {MAX_YEAR}")
        return val

    @field_validator("page", mode="before")
    @classmethod
    def validate_page(cls, v):
        if v is None:
            return 1
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"page must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("page must be >= 1")
        return val

    @field_validator("page_size", mode="before")
    @classmethod
    def validate_page_size(cls, v):
        if v is None:
            return 20
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"page_size must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("page_size must be >= 1")
        if val > MAX_PAGE_SIZE:
            raise ValueError(f"page_size cannot exceed {MAX_PAGE_SIZE}")
        return val

    @field_validator("sort_by", mode="before")
    @classmethod
    def validate_sort_by(cls, v):
        if v is None or v == "":
            return None
        if v not in ALLOWED_SORT_FIELDS:
            raise ValueError(
                f"sort_by must be one of {ALLOWED_SORT_FIELDS}, got '{v}'"
            )
        return v

    @field_validator("sort_order", mode="before")
    @classmethod
    def validate_sort_order(cls, v):
        if v is None or v == "":
            return "asc"
        v_lower = str(v).lower()
        if v_lower not in ALLOWED_SORT_ORDERS:
            raise ValueError(
                f"sort_order must be 'asc' or 'desc', got '{v}'"
            )
        return v_lower

    @field_validator("companies", mode="before")
    @classmethod
    def validate_companies(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("companies must be a list of strings")
        for idx, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"companies[{idx}] must be a non-empty string")
        return [item.strip() for item in v]

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_list(cls, v, info):
        if v is None:
            return v

        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list of strings")

        validated: list[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"{info.field_name}[{idx}] must be a non-empty string"
                )
            validated.append(item.strip())

        return validated

    @model_validator(mode="after")
    def validate_experience_range(self):
        if self.min_experience is not None and self.max_experience is not None:
            if self.min_experience > self.max_experience:
                raise ValueError(
                    f"min_experience ({self.min_experience}) cannot be greater "
                    f"than max_experience ({self.max_experience})"
                )
        return self

    @model_validator(mode="after")
    def validate_passout_year_range(self):
        if self.passout_start_year is not None and self.passout_end_year is not None:
            if self.passout_start_year > self.passout_end_year:
                raise ValueError(
                    f"passout_start_year ({self.passout_start_year}) cannot be "
                    f"greater than passout_end_year ({self.passout_end_year})"
                )
        return self
    

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EducationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    education_id: str
    education: str
    institution: Optional[str] = None
    percentage: Optional[float] = None
    year_of_passed: Optional[int] = None


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: str
    skill: str


class WorkExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: str
    role: str
    company_name: str
    company_location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_present: Optional[bool] = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    total_experience: Optional[int] = None
    education: List[EducationResponse] = []
    skills: List[SkillResponse] = []
    work_experience: List[WorkExperienceResponse] = []


class MasterDataItem(BaseModel):
    id: str
    name: str


class MasterDataResponse(BaseModel):
    status: str
    data: Dict[str, List[MasterDataItem]]


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str


# ---------------------------------------------------------------------------
# Dynamic filter schemas
# ---------------------------------------------------------------------------

class DynamicFilterRequest(BaseModel):
    """Request body for LLM-powered filter generation from natural language."""
    query: str

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("query must be a non-empty string")
        cleaned = v.strip()
        if len(cleaned) > 1000:
            raise ValueError("query must not exceed 1000 characters")
        return cleaned


class DynamicFilterResponse(BaseModel):
    """Structured filter payload returned by the LLM.

    Fields use human-readable names (not UUIDs) so the frontend can
    display them directly and persist them in localStorage.
    """
    skills: Optional[List[str]] = None
    education: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    min_experience: Optional[float] = None
    max_experience: Optional[float] = None
    name: Optional[str] = None
    passout_start_year: Optional[int] = None
    passout_end_year: Optional[int] = None
    percentage: Optional[float] = None

    @field_validator("min_experience", "max_experience", mode="before")
    @classmethod
    def coerce_experience(cls, v, info):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            match = re.search(r"(\d+(?:\.\d+)?)", v)
            if match:
                return float(match.group(1))
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator("passout_start_year", "passout_end_year", mode="before")
    @classmethod
    def coerce_passout_year(cls, v, info):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            match = re.search(r"(\d{4})", v)
            if match:
                return int(match.group(1))
            return None
        try:
            val = int(v)
            if MIN_YEAR <= val <= MAX_YEAR:
                return val
            return None
        except (ValueError, TypeError):
            return None

    @field_validator("percentage", mode="before")
    @classmethod
    def coerce_percentage(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            match = re.search(r"(\d+(?:\.\d+)?)", v)
            if match:
                val = float(match.group(1))
                return val if 0 <= val <= 100 else None
            return None
        try:
            val = float(v)
            return val if 0 <= val <= 100 else None
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------------------
# Natural-language search schemas
# ---------------------------------------------------------------------------

class NLSearchRequest(BaseModel):
    """Initial NL search: the LLM parses the query and a search_id is minted."""
    user_query: str
    page: Optional[int] = 1
    page_size: Optional[int] = 20
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"
    export: bool = False

    @field_validator("user_query", mode="before")
    @classmethod
    def validate_user_query(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("user_query must be a non-empty string")
        cleaned = v.strip()
        # if len(cleaned) > 1000:
        #     raise ValueError("user_query must not exceed 1000 characters")
        return cleaned

    @field_validator("page", mode="before")
    @classmethod
    def validate_nl_page(cls, v):
        if v is None:
            return 1
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"page must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("page must be >= 1")
        return val

    @field_validator("page_size", mode="before")
    @classmethod
    def validate_nl_page_size(cls, v):
        if v is None:
            return 20
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"page_size must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("page_size must be >= 1")
        if val > MAX_PAGE_SIZE:
            raise ValueError(f"page_size cannot exceed {MAX_PAGE_SIZE}")
        return val

    @field_validator("sort_by", mode="before")
    @classmethod
    def validate_nl_sort_by(cls, v):
        if v is None or v == "":
            return None
        if v not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"sort_by must be one of {ALLOWED_SORT_FIELDS}, got '{v}'")
        return v

    @field_validator("sort_order", mode="before")
    @classmethod
    def validate_nl_sort_order(cls, v):
        if v is None or v == "":
            return "asc"
        v_lower = str(v).lower()
        if v_lower not in ALLOWED_SORT_ORDERS:
            raise ValueError(f"sort_order must be 'asc' or 'desc', got '{v}'")
        return v_lower


class NLSearchPaginateRequest(BaseModel):
    """Follow-up paginated request: reuses cached filters via search_id."""
    search_id: str
    page: Optional[int] = 1
    page_size: Optional[int] = 20
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"

    @field_validator("search_id", mode="before")
    @classmethod
    def validate_search_id(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("search_id must be a non-empty string")
        return v.strip()

    @field_validator("page", mode="before")
    @classmethod
    def validate_nlp_page(cls, v):
        if v is None:
            return 1
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"page must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("page must be >= 1")
        return val

    @field_validator("page_size", mode="before")
    @classmethod
    def validate_nlp_page_size(cls, v):
        if v is None:
            return 20
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"page_size must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("page_size must be >= 1")
        if val > MAX_PAGE_SIZE:
            raise ValueError(f"page_size cannot exceed {MAX_PAGE_SIZE}")
        return val

    @field_validator("sort_by", mode="before")
    @classmethod
    def validate_nlp_sort_by(cls, v):
        if v is None or v == "":
            return None
        if v not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"sort_by must be one of {ALLOWED_SORT_FIELDS}, got '{v}'")
        return v

    @field_validator("sort_order", mode="before")
    @classmethod
    def validate_nlp_sort_order(cls, v):
        if v is None or v == "":
            return "asc"
        v_lower = str(v).lower()
        if v_lower not in ALLOWED_SORT_ORDERS:
            raise ValueError(f"sort_order must be 'asc' or 'desc', got '{v}'")
        return v_lower


class NLSearchResponse(BaseModel):
    """Wrapper returned by the NL search endpoint."""
    status: str = "success"
    search_id: str
    user_query: Optional[str] = None
    filters_applied: Optional[Dict[str, Any]] = None
    candidates: List[Dict[str, Any]] = []
    total_record: int = 0
    page: int = 1
    page_size: int = 20


class CombinedFilterPayload(BaseModel):
    """Top-level request body accepted by ``POST /filter_resumes``.

    *   ``filters`` – standard dropdown/UI-driven filters (UUIDs for
        skills, education, roles).
    *   ``dynamic_filters`` – LLM-generated filters (human-readable
        names). The backend resolves names to UUIDs before querying.
    """
    filters: Optional[Dict[str, Any]] = None
    dynamic_filters: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def at_least_one(self):
        f = self.filters or {}
        d = self.dynamic_filters or {}
        has_filters = any(
            v for k, v in f.items()
            if k not in ("action_type", "page", "page_size", "sort_by", "sort_order")
        )
        has_dynamic = bool(d)
        if not has_filters and not has_dynamic:
            raise ValueError(
                "At least one of 'filters' or 'dynamic_filters' must contain filter criteria"
            )
        return self