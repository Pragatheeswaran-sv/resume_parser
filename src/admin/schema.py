from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

class AdminCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class AuthorizedUserCreate(BaseModel):
    email: str
    password: str
    connect_with: dict

# class ModelConfigRequest(BaseModel):
#     model_version_id: Optional[str] = None
#     model_id: Optional[str] = None
#     # admin_id: Optional[str] = None
#     apikey: Optional[str] = None
#     version: Optional[str] = None
#     max_tokens: Optional[int] = None
#     temperature: Optional[float] = None