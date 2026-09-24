import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import summarize_resume
from app.errors import AppError
from app.integrations.service import decrypt_key, get_settings_row
from app.profiles.models import Profile
from app.profiles.resume_text import extract_resume_text
from app.profiles.schemas import ProfileCreate, ProfileUpdate


async def list_profiles(db: AsyncSession, *, client_id: UUID) -> list[Profile]:
    result = await db.execute(
        select(Profile).where(Profile.client_id == client_id).order_by(Profile.created_at.desc())
    )
    return list(result.scalars().all())


async def get_profile(db: AsyncSession, profile_id: UUID) -> Profile:
    profile = await db.get(Profile, profile_id)
    if profile is None:
        raise AppError("not_found", "Resume type not found", 404)
    return profile


async def get_profile_scoped(db: AsyncSession, profile_id: UUID, *, client_id: UUID) -> Profile:
    profile = await get_profile(db, profile_id)
    if profile.client_id != client_id:
        raise AppError("not_found", "Resume type not found", 404)
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
    await db.delete(profile)
    await db.commit()


async def upload_resume(
    db: AsyncSession, profile: Profile, *, filename: str, data: bytes
) -> Profile:
    """Extracts the resume's text, has the client's OpenAI key summarize it, and stores only
    the summary + key skills. Replaces any earlier resume for this resume type."""
    text = await asyncio.to_thread(extract_resume_text, filename, data)

    ai_settings = await get_settings_row(db, profile.client_id)
    if ai_settings is None:
        raise AppError(
            "no_api_key",
            "Add an OpenAI API key under Integrations before uploading resumes.",
            400,
        )
    summary = await summarize_resume(
        api_key=decrypt_key(ai_settings.api_key_encrypted),
        model=ai_settings.model,
        resume_text=text,
    )

    profile.resume_filename = filename[:255]
    profile.resume_summary = summary.summary
    profile.skills = summary.key_skills
    profile.resume_uploaded_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(profile)
    return profile
