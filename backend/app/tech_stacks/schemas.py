from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TechStackCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TechStackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class TechStackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_active: bool
    created_at: datetime
