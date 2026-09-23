from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.profiles.models import Profile
from app.profiles.schemas import ProfileCreate, ProfileUpdate
from app.tech_stacks.service import ensure_all_active as ensure_tech_stacks_active


async def list_profiles(db: AsyncSession, *, client_id: UUID) -> list[Profile]:
    result = await db.execute(
        select(Profile).where(Profile.client_id == client_id).order_by(Profile.created_at.desc())
    )
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
    await ensure_tech_stacks_active(db, payload.tech_stacks)
    profile = Profile(client_id=client_id, **payload.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_profile(db: AsyncSession, profile: Profile, payload: ProfileUpdate) -> Profile:
    data = payload.model_dump(exclude_unset=True)
    if data.get("tech_stacks"):
        await ensure_tech_stacks_active(db, data["tech_stacks"])
    for field, value in data.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_profile(db: AsyncSession, profile: Profile) -> None:
    await db.delete(profile)
    await db.commit()
