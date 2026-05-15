from pydantic import BaseModel, field_validator
from typing import List, Optional, Literal
from uuid import UUID

class RoundInsertRequest(BaseModel):
    # round_id: UUID
    round_name: str