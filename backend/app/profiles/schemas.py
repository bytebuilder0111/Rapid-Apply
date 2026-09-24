from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    is_active: bool | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    name: str
    skills: list[str]
    notes: str | None
    resume_filename: str | None
    resume_summary: str | None
    resume_uploaded_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
