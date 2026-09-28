import hashlib
import re
from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import analyze_job_description
from app.analysis.duplicates import Entry, find_duplicate
from app.analysis.models import Analysis, JobHistory
from app.analysis.schemas import AnalysisOut, AnalyzeRequest, SaveAnalysisRequest
from app.errors import AppError
from app.integrations.service import get_decrypted_key_for_client, get_settings_row
from app.models import Role, User
from app.profiles.models import Profile
from app.resume_types.models import ResumeType
from app.sheets.service import initial_record_status, recorded_jobs


def normalize_jd_hash(job_description: str) -> str:
    normalized = re.sub(r"\s+", " ", job_description.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()


async def _resolve_profile(
    db: AsyncSession, *, user: User, client_id: UUID, profile_id: UUID | None
) -> Profile:
    """The profile (person) to work with: a bidder's assigned one, or the client's choice."""
    if user.role == Role.BIDDER:
        profile_id = user.assigned_profile_id
        if profile_id is None:
            raise AppError("no_assigned_profile", "You have no assigned profile yet", 400)
    elif profile_id is None:
        raise AppError("profile_required", "Choose a profile first", 400)
    profile = await db.get(Profile, profile_id)
    if profile is None or profile.client_id != client_id:
        raise AppError("invalid_profile", "Profile does not belong to this client", 400)
    return profile


async def _resumes_context(db: AsyncSession, profile_id: UUID) -> list[dict]:
    """The profile's active resume types that have an uploaded resume summary to match on."""
    result = await db.execute(
        select(ResumeType).where(
            ResumeType.profile_id == profile_id,
            ResumeType.is_active.is_(True),
            ResumeType.resume_summary.is_not(None),
        )
    )
    return [
        {"id": str(r.id), "name": r.name, "summary": r.resume_summary, "skills": r.skills}
        for r in result.scalars().all()
    ]


async def _find_duplicate(
    db: AsyncSession, *, user: User, client_id: UUID, profile: Profile, payload
) -> str | None:
    """Checks the job against this profile's saved analyses, imported history, then its
    bid sheet."""
    rows = await db.execute(
        select(
            Analysis.company_name, Analysis.position_name, Analysis.job_link, Analysis.created_at
        ).where(Analysis.client_id == client_id, Analysis.profile_id == profile.id)
    )
    entries = [
        Entry(
            company=company,
            position=position,
            job_link=job_link or "",
            where=f"saved for {profile.name} on {created:%Y-%m-%d}",
        )
        for company, position, job_link, created in rows.all()
    ]
    history = await db.execute(
        select(
            JobHistory.company_name,
            JobHistory.position_name,
            JobHistory.job_link,
            JobHistory.applied_on,
            JobHistory.source,
        ).where(JobHistory.client_id == client_id, JobHistory.profile_id == profile.id)
    )
    entries += [
        Entry(
            company=company,
            position=position,
            job_link=job_link or "",
            where=f"{profile.name}'s history, {source}"
            + (f", applied {applied:%Y-%m-%d}" if applied else ""),
        )
        for company, position, job_link, applied, source in history.all()
    ]
    entries += await recorded_jobs(db, client_id=client_id, profile_id=profile.id, user=user)
    return find_duplicate(
        entries,
        company=payload.company_name,
        position=payload.position_name,
        job_link=payload.job_link,
    )


async def _reject_duplicate(
    db: AsyncSession, *, user: User, client_id: UUID, profile: Profile, payload
) -> None:
    reason = await _find_duplicate(
        db, user=user, client_id=client_id, profile=profile, payload=payload
    )
    if reason:
        raise AppError("duplicate_job", f"Duplicate job: {reason}", 409)


async def analyze(db: AsyncSession, *, user: User, client_id: UUID, payload: AnalyzeRequest):
    ai_settings = await get_settings_row(db, client_id)
    if ai_settings is None:
        raise AppError("no_api_key", "No OpenAI API key configured for this client", 400)
    api_key = await get_decrypted_key_for_client(db, client_id)

    profile = await _resolve_profile(
        db, user=user, client_id=client_id, profile_id=payload.profile_id
    )
    resumes = await _resumes_context(db, profile.id)
    if not resumes:
        raise AppError(
            "no_resumes",
            f"{profile.name} has no uploaded resumes yet. Upload one under Resume Types first.",
            400,
        )
    # Before the AI call, so a duplicate costs nothing.
    await _reject_duplicate(db, user=user, client_id=client_id, profile=profile, payload=payload)
    return await analyze_job_description(
        api_key=api_key,
        model=ai_settings.model,
        job_description=payload.job_description,
        resumes=resumes,
    )


async def save_analysis(
    db: AsyncSession, *, user: User, client_id: UUID, payload: SaveAnalysisRequest
) -> AnalysisOut:
    if payload.result.skip_reason:
        raise AppError(
            "skipped_jd",
            f"This job was skipped, so it can't be saved: {payload.result.skip_reason}",
            400,
        )
    if not payload.result.recommended_resume_type_id:
        raise AppError(
            "dismatched_jd", "A Dismatched JD has no matching resume, so it can't be saved.", 400
        )
    profile = await _resolve_profile(
        db, user=user, client_id=client_id, profile_id=payload.profile_id
    )
    # Checked again at save: the sheet may have changed since Analyze.
    await _reject_duplicate(db, user=user, client_id=client_id, profile=profile, payload=payload)
    selected_resume_type_id = payload.selected_resume_type_id
    if selected_resume_type_id is not None:
        resume_type = await db.get(ResumeType, selected_resume_type_id)
        if resume_type is None or resume_type.profile_id != profile.id:
            raise AppError("invalid_resume_type", "That resume isn't in this profile", 400)

    record_status = await initial_record_status(
        db, client_id=client_id, profile_id=profile.id, user=user
    )

    analysis = Analysis(
        client_id=client_id,
        created_by=user.id,
        company_name=payload.company_name,
        position_name=payload.position_name,
        job_description=payload.job_description,
        jd_hash=normalize_jd_hash(payload.job_description),
        job_link=payload.job_link,
        profile_id=profile.id,
        recommended_resume_type_id=(
            UUID(payload.result.recommended_resume_type_id)
            if payload.result.recommended_resume_type_id
            else None
        ),
        selected_resume_type_id=selected_resume_type_id,
        result=payload.result.model_dump(),
        model=payload.model,
        prompt_version=payload.prompt_version,
        tokens=payload.tokens,
        latency_ms=payload.latency_ms,
        record_status=record_status,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return await _to_out(db, analysis)


def _build_out(analysis: Analysis, *, creator_name: str) -> AnalysisOut:
    return AnalysisOut(
        id=analysis.id,
        client_id=analysis.client_id,
        created_by=analysis.created_by,
        created_by_name=creator_name,
        company_name=analysis.company_name,
        position_name=analysis.position_name,
        job_description=analysis.job_description,
        job_link=analysis.job_link,
        profile_id=analysis.profile_id,
        recommended_resume_type_id=analysis.recommended_resume_type_id,
        selected_resume_type_id=analysis.selected_resume_type_id,
        result=analysis.result,
        model=analysis.model,
        prompt_version=analysis.prompt_version,
        tokens=analysis.tokens,
        latency_ms=analysis.latency_ms,
        record_status=analysis.record_status,
        record_attempts=analysis.record_attempts,
        record_error=analysis.record_error,
        created_at=analysis.created_at,
    )


async def _to_out(db: AsyncSession, analysis: Analysis) -> AnalysisOut:
    creator = await db.get(User, analysis.created_by)
    return _build_out(analysis, creator_name=creator.name if creator else "Unknown")


async def list_analyses(
    db: AsyncSession,
    *,
    client_id: UUID,
    created_by: UUID | None,
    search: str | None,
    profile_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> list[AnalysisOut]:
    stmt = select(Analysis).where(Analysis.client_id == client_id)
    if created_by is not None:
        stmt = stmt.where(Analysis.created_by == created_by)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Analysis.company_name.ilike(pattern) | Analysis.position_name.ilike(pattern)
        )
    if profile_id is not None:
        stmt = stmt.where(Analysis.profile_id == profile_id)
    if date_from is not None:
        stmt = stmt.where(Analysis.created_at >= datetime.combine(date_from, time.min, UTC))
    if date_to is not None:
        stmt = stmt.where(Analysis.created_at <= datetime.combine(date_to, time.max, UTC))
    stmt = stmt.order_by(Analysis.created_at.desc())

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    if not rows:
        return []

    creator_ids = {row.created_by for row in rows}
    creators = await db.execute(select(User.id, User.name).where(User.id.in_(creator_ids)))
    names_by_id = dict(creators.all())

    return [
        _build_out(row, creator_name=names_by_id.get(row.created_by, "Unknown")) for row in rows
    ]


async def get_analysis(db: AsyncSession, analysis_id: UUID, *, client_id: UUID) -> AnalysisOut:
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None or analysis.client_id != client_id:
        raise AppError("not_found", "Analysis not found", 404)
    return await _to_out(db, analysis)
