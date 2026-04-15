from pydantic import BaseModel
from typing import List

class EmailRequest(BaseModel):
    email_id: str

class EmailFetchResult(BaseModel):
    email: str
    source: str
    status: str


class EmailFetchResponse(BaseModel):
    message: str
    results: List[EmailFetchResult]