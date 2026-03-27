from pydantic import BaseModel
from typing import List, Optional

class ResumeFilterRequest(BaseModel):
    action_type: str = "filter"
    name: Optional[str] = None
    file_name: Optional[str] = None
    min_experience: Optional[float] = None
    max_experience: Optional[float] = None
    skills: Optional[List[str]] = None  # UUIDs preferred: ["...", "..."]
    education: Optional[List[str]] = None  # UUIDs preferred
    roles: Optional[List[str]] = None  # UUIDs preferred
    companies: Optional[List[str]] = None
    passout_start_year: Optional[int] = None
    passout_end_year: Optional[int] = None
    percentage: Optional[float] = None
    page: Optional[int] = 1
    page_size: Optional[int] = 20
    sort_by: Optional[str] = None  # candidate fields: name, total_experience, created_at
    sort_order: Optional[str] = "asc"

class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5