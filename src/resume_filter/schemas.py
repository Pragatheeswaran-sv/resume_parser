from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Any, Dict, List, Optional


ALLOWED_SORT_FIELDS = {"name", "total_experience", "created_at", "updated_at"}
ALLOWED_SORT_ORDERS = {"asc", "desc"}
MAX_PAGE_SIZE = 100
MIN_YEAR = 1950
MAX_YEAR = 2100


class ResumeFilterRequest(BaseModel):
    action_type: str = "filter"
    name: Optional[str] = None
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
    def validate_uuid_lists(cls, v, info):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list of UUID strings")
        validated: list[str] = []
        for idx, item in enumerate(v):
            try:
                validated.append(str(UUID(str(item))))
            except (ValueError, AttributeError):
                raise ValueError(
                    f"{info.field_name}[{idx}] = '{item}' is not a valid UUID"
                )
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

    @field_validator("name", "file_name", mode="before")
    @classmethod
    def validate_string_fields(cls, v, info):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        cleaned = v.strip()
        if len(cleaned) > 255:
            raise ValueError(f"{info.field_name} must not exceed 255 characters")
        return cleaned if cleaned else None

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


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("query must be a non-empty string")
        cleaned = v.strip()
        if len(cleaned) > 1000:
            raise ValueError("query must not exceed 1000 characters")
        return cleaned

    @field_validator("top_k", mode="before")
    @classmethod
    def validate_top_k(cls, v):
        if v is None:
            return 5
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"top_k must be a positive integer, got '{v}'")
        if val < 1:
            raise ValueError("top_k must be >= 1")
        if val > 50:
            raise ValueError("top_k cannot exceed 50")
        return val


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


class SemanticSearchResultItem(BaseModel):
    id: str
    name: Optional[str] = None
    file_name: Optional[str] = None
    experience: Optional[float] = 0.0
    skills: List[Any] = []