from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, require_roles, scope_client_id
from app.errors import AppError
from app.models import Role, User
from app.profiles import service
from app.profiles.schemas import ProfileCreate, ProfileOut, ProfileUpdate

router = APIRouter()


def _resolve_scope(user: User, requested_client_id: UUID | None) -> UUID:
    """Which client's profiles this request may touch. Only ADMIN may pass client_id."""
    own_scope = scope_client_id(user)
    if user.role == Role.ADMIN:
        if requested_client_id is None:
            raise AppError("client_id_required", "client_id is required for admin requests", 400)
        return requested_client_id
    return own_scope  # CLIENT -> their own id; BIDDER -> their client's id


@router.get("", response_model=list[ProfileOut])
async def list_profiles(
    client_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProfileOut]:
    scope = _resolve_scope(user, client_id)
    profiles = await service.list_profiles(db, client_id=scope)
    return [ProfileOut.model_validate(p) for p in profiles]


@router.post("", response_model=ProfileOut, status_code=201)
async def create_profile(
    payload: ProfileCreate,
    user: User = Depends(require_roles(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    profile = await service.create_profile(db, client_id=user.id, payload=payload)
    return ProfileOut.model_validate(profile)


@router.get("/{profile_id}", response_model=ProfileOut)
async def get_profile(
    profile_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    if user.role == Role.ADMIN:
        profile = await service.get_profile(db, profile_id)
    else:
        profile = await service.get_profile_scoped(db, profile_id, client_id=scope_client_id(user))
    return ProfileOut.model_validate(profile)


@router.patch("/{profile_id}", response_model=ProfileOut)
async def update_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    if user.role == Role.ADMIN:
        profile = await service.get_profile(db, profile_id)
    elif user.role == Role.CLIENT:
        profile = await service.get_profile_scoped(db, profile_id, client_id=user.id)
    else:
        raise AppError("forbidden", "Not allowed", 403)
    profile = await service.update_profile(db, profile, payload)
    return ProfileOut.model_validate(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user.role == Role.ADMIN:
        profile = await service.get_profile(db, profile_id)
    elif user.role == Role.CLIENT:
        profile = await service.get_profile_scoped(db, profile_id, client_id=user.id)
    else:
        raise AppError("forbidden", "Not allowed", 403)
    await service.delete_profile(db, profile)
