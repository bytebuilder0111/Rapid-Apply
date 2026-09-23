import hashlib
import re
from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import analyze_job_description
from app.analysis.models import Analysis
from app.analysis.schemas import AnalysisOut, AnalyzeRequest, SaveAnalysisRequest
from app.errors import AppError
from app.integrations.service import get_decrypted_key_for_client, get_settings_row
from app.models import Role, User
from app.profiles.models import Profile
from app.sheets.service import initial_record_status


def normalize_jd_hash(job_description: str) -> str:
    normalized = re.sub(r"\s+", " ", job_description.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()


async def _active_profiles_context(db: AsyncSession, client_id: UUID) -> list[dict]:
    result = await db.execute(
        select(Profile).where(Profile.client_id == client_id, Profile.is_active.is_(True))
    )
    return [
        {"id": str(p.id), "name": p.name, "tech_stacks": p.tech_stacks}
        for p in result.scalars().all()
    ]


async def _check_duplicate(
    db: AsyncSession, *, client_id: UUID, job_link: str | None, jd_hash: str
) -> str | None:
    if job_link:
        result = await db.execute(
            select(Analysis.id).where(
                Analysis.client_id == client_id, Analysis.job_link == job_link
            )
        )
        if result.scalar_one_or_none() is not None:
            return "This job link was already analyzed for this client."
    result = await db.execute(
        select(Analysis.id).where(Analysis.client_id == client_id, Analysis.jd_hash == jd_hash)
    )
    if result.scalar_one_or_none() is not None:
        return "An identical job description was already analyzed for this client."
    return None


async def analyze(db: AsyncSession, *, user: User, client_id: UUID, payload: AnalyzeRequest):
    ai_settings = await get_settings_row(db, client_id)
    if ai_settings is None:
        raise AppError("no_api_key", "No OpenAI API key configured for this client", 400)
    api_key = await get_decrypted_key_for_client(db, client_id)

    profiles = await _active_profiles_context(db, client_id)
    outcome = await analyze_job_description(
        api_key=api_key,
        model=ai_settings.model,
        job_description=payload.job_description,
        profiles=profiles,
    )

    jd_hash = normalize_jd_hash(payload.job_description)
    duplicate_reason = await _check_duplicate(
        db, client_id=client_id, job_link=payload.job_link, jd_hash=jd_hash
    )

    return outcome, duplicate_reason


async def save_analysis(
    db: AsyncSession, *, user: User, client_id: UUID, payload: SaveAnalysisRequest
) -> AnalysisOut:
    selected_profile_id = payload.selected_profile_id
    if user.role == Role.BIDDER:
        # A bidder can only ever save under their one assigned profile.
        selected_profile_id = user.assigned_profile_id

    if selected_profile_id is not None:
        profile = await db.get(Profile, selected_profile_id)
        if profile is None or profile.client_id != client_id:
            raise AppError("invalid_profile", "Profile does not belong to this client", 400)

    record_status = await initial_record_status(
        db, client_id=client_id, profile_id=selected_profile_id, user=user
    )

    analysis = Analysis(
        client_id=client_id,
        created_by=user.id,
        company_name=payload.company_name,
        position_name=payload.position_name,
        job_description=payload.job_description,
        jd_hash=normalize_jd_hash(payload.job_description),
        job_link=payload.job_link,
        recommended_profile_id=(
            UUID(payload.result.recommended_profile_id)
            if payload.result.recommended_profile_id
            else None
        ),
        selected_profile_id=selected_profile_id,
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


async def _to_out(db: AsyncSession, analysis: Analysis) -> AnalysisOut:
    creator = await db.get(User, analysis.created_by)
    return AnalysisOut(
        id=analysis.id,
        client_id=analysis.client_id,
        created_by=analysis.created_by,
        created_by_name=creator.name if creator else "Unknown",
        company_name=analysis.company_name,
        position_name=analysis.position_name,
        job_description=analysis.job_description,
        job_link=analysis.job_link,
        recommended_profile_id=analysis.recommended_profile_id,
        selected_profile_id=analysis.selected_profile_id,
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
        stmt = stmt.where(Analysis.selected_profile_id == profile_id)
    if date_from is not None:
        stmt = stmt.where(Analysis.created_at >= datetime.combine(date_from, time.min, UTC))
    if date_to is not None:
        stmt = stmt.where(Analysis.created_at <= datetime.combine(date_to, time.max, UTC))
    stmt = stmt.order_by(Analysis.created_at.desc())

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return [await _to_out(db, row) for row in rows]


async def get_analysis(db: AsyncSession, analysis_id: UUID, *, client_id: UUID) -> AnalysisOut:
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None or analysis.client_id != client_id:
        raise AppError("not_found", "Analysis not found", 404)
    return await _to_out(db, analysis)
