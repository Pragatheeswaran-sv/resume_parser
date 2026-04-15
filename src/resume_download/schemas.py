"""Pydantic schemas for resume download and preview endpoints."""

from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator


class MultiDownloadRequest(BaseModel):
    resumeIds: List[str]
    format: Optional[Literal["pdf", "original"]] = "original"

    @field_validator("resumeIds")
    @classmethod
    def at_least_one_id(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("resumeIds must contain at least one ID")
        if len(v) > 50:
            raise ValueError("Cannot request more than 50 resumes at once")
        return v


class MultiDownloadItem(BaseModel):
    resumeId: str
    downloadUrl: str


class MultiDownloadResponse(BaseModel):
    status: str = "success"
    data: List[MultiDownloadItem]
