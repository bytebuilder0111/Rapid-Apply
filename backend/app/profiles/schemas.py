from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # Each entry validated against the live, admin-managed tech_stacks table — see
    # app/profiles/service.py, not a fixed Literal, so admins can add/remove stacks.
    tech_stacks: list[str] = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    notes: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    tech_stacks: list[str] | None = Field(default=None, min_length=1)
    skills: list[str] | None = None
    notes: str | None = None
    is_active: bool | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    name: str
    tech_stacks: list[str]
    skills: list[str]
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
