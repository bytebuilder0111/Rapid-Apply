from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models import Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    role: Role
    client_id: UUID | None
    assigned_profile_id: UUID | None
    is_active: bool
    created_at: datetime
