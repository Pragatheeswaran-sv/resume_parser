from pydantic import BaseModel, field_validator
from typing import Literal, Optional

class UserDashboardResponse(BaseModel):
    status: int
    message: str
    data: dict