from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime


class ClientCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)


class ClientUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)


class BidderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    is_active: bool
    client_id: UUID
    assigned_profile_id: UUID | None
    created_at: datetime


class BidderCreate(BaseModel):
    client_id: UUID
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    assigned_profile_id: UUID


class BidderUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    assigned_profile_id: UUID | None = None


class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class RoleCounts(BaseModel):
    total: int
    last_7_days: int
    last_30_days: int


class DashboardOut(BaseModel):
    clients: RoleCounts
    bidders: RoleCounts
