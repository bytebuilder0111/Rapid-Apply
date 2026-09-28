from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.users.usernames import Username


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    name: str
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime


class ClientCreate(BaseModel):
    username: Username
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


class ClientUpdate(BaseModel):
    username: Username | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)


class BidderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    name: str
    is_active: bool
    client_id: UUID
    assigned_profile_id: UUID | None
    created_at: datetime


class BidderCreate(BaseModel):
    """The bidder's client is the assigned profile's client; the name defaults to the
    username."""

    username: Username
    password: str = Field(min_length=1)
    assigned_profile_id: UUID
    name: str | None = Field(default=None, max_length=255)


class BidderUpdate(BaseModel):
    username: Username | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    assigned_profile_id: UUID | None = None


class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)


class RoleCounts(BaseModel):
    total: int
    last_7_days: int
    last_30_days: int


class DashboardOut(BaseModel):
    clients: RoleCounts
    bidders: RoleCounts
