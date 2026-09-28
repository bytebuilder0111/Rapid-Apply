from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResumeTypeCreate(BaseModel):
    profile_id: UUID
    name: str = Field(min_length=1, max_length=255)


class ResumeTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class ResumeTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    profile_id: UUID
    name: str
    skills: list[str]
    resume_filename: str | None
    resume_summary: str | None
    resume_uploaded_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
