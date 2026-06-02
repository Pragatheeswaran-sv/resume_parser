import re
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Any, Dict, List, Optional

class TailorResumeRequest(BaseModel):
    profile_summary: Optional[str]
    skills: List[str]
    workExperience : List