from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.profiles.models import Profile
from app.profiles.schemas import ProfileCreate, ProfileUpdate


async def list_profiles(db: AsyncSession, *, client_id: UUID | None) -> list[Profile]:
    """One client's profiles, or every client's when client_id is None (admin only)."""
    stmt = select(Profile).order_by(Profile.created_at)
    if client_id is not None:
        stmt = stmt.where(Profile.client_id == client_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_profile(db: AsyncSession, profile_id: UUID) -> Profile:
    profile = await db.get(Profile, profile_id)
    if profile is None:
        raise AppError("not_found", "Profile not found", 404)
    return profile


async def get_profile_scoped(db: AsyncSession, profile_id: UUID, *, client_id: UUID) -> Profile:
    profile = await get_profile(db, profile_id)
    if profile.client_id != client_id:
        raise AppError("not_found", "Profile not found", 404)
    return profile


async def create_profile(db: AsyncSession, *, client_id: UUID, payload: ProfileCreate) -> Profile:
    profile = Profile(client_id=client_id, **payload.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_profile(db: AsyncSession, profile: Profile, payload: ProfileUpdate) -> Profile:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_profile(db: AsyncSession, profile: Profile) -> None:
    # Its resume types and sheet configs go with it (ON DELETE CASCADE); assigned bidders
    # and past analyses keep their rows with the reference set to NULL.
    await db.delete(profile)
    await db.commit()
