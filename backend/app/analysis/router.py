from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import service
from app.analysis.models import RecordStatus
from app.analysis.schemas import (
    AnalysisOut,
    AnalyzeRequest,
    AnalyzeResponse,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    SaveAnalysisRequest,
)
from app.db import get_db
from app.deps import get_current_user, require_roles, scope_client_id
from app.errors import AppError
from app.models import Role, User
from app.sheets.service import record_analysis

router = APIRouter(dependencies=[Depends(require_roles(Role.CLIENT, Role.BIDDER))])


@router.post("/check-duplicate", response_model=DuplicateCheckResponse)
async def check_duplicate(
    payload: DuplicateCheckRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DuplicateCheckResponse:
    client_id = scope_client_id(user)
    assert client_id is not None
    reason = await service.check_duplicate(db, user=user, client_id=client_id, payload=payload)
    return DuplicateCheckResponse(duplicate=reason)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    client_id = scope_client_id(user)
    assert client_id is not None
    outcome = await service.analyze(db, user=user, client_id=client_id, payload=payload)
    return AnalyzeResponse(
        result=outcome.result,
        model=outcome.model,
        prompt_version=outcome.prompt_version,
        tokens=outcome.tokens,
        latency_ms=outcome.latency_ms,
    )


@router.post("", response_model=AnalysisOut, status_code=201)
async def save_analysis(
    payload: SaveAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    client_id = scope_client_id(user)
    assert client_id is not None
    analysis = await service.save_analysis(db, user=user, client_id=client_id, payload=payload)
    if analysis.record_status == RecordStatus.PENDING:
        background_tasks.add_task(record_analysis, analysis.id)
    return analysis


@router.get("", response_model=list[AnalysisOut])
async def list_analyses(
    search: str | None = Query(default=None),
    profile_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnalysisOut]:
    client_id = scope_client_id(user)
    assert client_id is not None
    # A bidder sees only their own analyses; the owning client sees all of them.
    created_by = user.id if user.role == Role.BIDDER else None
    return await service.list_analyses(
        db,
        client_id=client_id,
        created_by=created_by,
        search=search,
        profile_id=profile_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    client_id = scope_client_id(user)
    assert client_id is not None
    return await service.get_analysis(db, analysis_id, client_id=client_id)


@router.post("/{analysis_id}/retry", response_model=AnalysisOut)
async def retry_record(
    analysis_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisOut:
    client_id = scope_client_id(user)
    assert client_id is not None
    existing = await service.get_analysis(db, analysis_id, client_id=client_id)
    if existing.record_status != RecordStatus.FAILED:
        raise AppError("not_retryable", "Only a failed sheet write can be retried", 400)
    await record_analysis(analysis_id)
    return await service.get_analysis(db, analysis_id, client_id=client_id)
