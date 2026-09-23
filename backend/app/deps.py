from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_access_token
from app.db import get_db
from app.errors import AppError
from app.models import Role, User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AppError("unauthorized", "Not authenticated", 401)

    payload = decode_access_token(credentials.credentials)
    user = await db.get(User, UUID(payload["sub"]))
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AppError("unauthorized", "Not authenticated", 401)
    return user


def require_roles(*roles: Role):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError("forbidden", "Not allowed", 403)
        return user

    return checker


def scope_client_id(user: User) -> UUID | None:
    """The client_id future feature routers should filter by. None means no filter (ADMIN)."""
    if user.role == Role.ADMIN:
        return None
    if user.role == Role.CLIENT:
        return user.id
    return user.client_id
