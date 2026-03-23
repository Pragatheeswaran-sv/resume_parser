from pydantic import BaseModel
from typing import List, Optional

class ResumeFilterRequest(BaseModel):
    action_type:str = "filter"
    name: Optional[str] = None
    file_name: Optional[str] = None
    min_experience: Optional[float] = None
    max_experience: Optional[float] = None
    skills: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    education_keywords: Optional[List[str]] = None

class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5