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