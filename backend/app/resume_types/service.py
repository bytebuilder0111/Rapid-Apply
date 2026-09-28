import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import summarize_resume
from app.errors import AppError
from app.integrations.service import decrypt_key, get_settings_row
from app.profiles.models import Profile
from app.resume_types.models import ResumeType
from app.resume_types.resume_text import extract_resume_text
from app.resume_types.schemas import ResumeTypeCreate, ResumeTypeUpdate


async def list_resume_types(
    db: AsyncSession, *, client_id: UUID, profile_id: UUID | None = None
) -> list[ResumeType]:
    stmt = select(ResumeType).where(ResumeType.client_id == client_id)
    if profile_id is not None:
        stmt = stmt.where(ResumeType.profile_id == profile_id)
    result = await db.execute(stmt.order_by(ResumeType.created_at))
    return list(result.scalars().all())


async def get_resume_type(db: AsyncSession, resume_type_id: UUID) -> ResumeType:
    resume_type = await db.get(ResumeType, resume_type_id)
    if resume_type is None:
        raise AppError("not_found", "Resume type not found", 404)
    return resume_type


async def get_resume_type_scoped(
    db: AsyncSession, resume_type_id: UUID, *, client_id: UUID
) -> ResumeType:
    resume_type = await get_resume_type(db, resume_type_id)
    if resume_type.client_id != client_id:
        raise AppError("not_found", "Resume type not found", 404)
    return resume_type


async def create_resume_type(
    db: AsyncSession, *, client_id: UUID, payload: ResumeTypeCreate
) -> ResumeType:
    profile = await db.get(Profile, payload.profile_id)
    if profile is None or profile.client_id != client_id:
        raise AppError("not_found", "Profile not found", 404)
    resume_type = ResumeType(client_id=client_id, profile_id=profile.id, name=payload.name)
    db.add(resume_type)
    await db.commit()
    await db.refresh(resume_type)
    return resume_type


async def update_resume_type(
    db: AsyncSession, resume_type: ResumeType, payload: ResumeTypeUpdate
) -> ResumeType:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resume_type, field, value)
    await db.commit()
    await db.refresh(resume_type)
    return resume_type


async def delete_resume_type(db: AsyncSession, resume_type: ResumeType) -> None:
    await db.delete(resume_type)
    await db.commit()


async def upload_resume(
    db: AsyncSession, resume_type: ResumeType, *, filename: str, data: bytes
) -> ResumeType:
    """Extracts the resume's text, has the client's OpenAI key summarize it, and stores only
    the summary + key skills. Replaces any earlier resume for this resume type."""
    text = await asyncio.to_thread(extract_resume_text, filename, data)

    ai_settings = await get_settings_row(db, resume_type.client_id)
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

    resume_type.resume_filename = filename[:255]
    resume_type.resume_summary = summary.summary
    resume_type.skills = summary.key_skills
    resume_type.resume_uploaded_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume_type)
    return resume_type
