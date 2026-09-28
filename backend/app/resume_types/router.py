from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, require_roles, scope_client_id
from app.errors import AppError
from app.models import Role, User
from app.resume_types import service
from app.resume_types.resume_text import MAX_UPLOAD_BYTES
from app.resume_types.schemas import ResumeTypeCreate, ResumeTypeOut, ResumeTypeUpdate

router = APIRouter()


@router.get("", response_model=list[ResumeTypeOut])
async def list_resume_types(
    profile_id: UUID | None = Query(default=None),
    client_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeTypeOut]:
    if user.role == Role.ADMIN:
        if client_id is None:
            raise AppError("client_id_required", "client_id is required for admin requests", 400)
        scope = client_id
    else:
        scope = scope_client_id(user)
        assert scope is not None
    if user.role == Role.BIDDER:
        # A bidder only ever works with their one assigned profile's resumes.
        if user.assigned_profile_id is None:
            return []
        profile_id = user.assigned_profile_id
    rows = await service.list_resume_types(db, client_id=scope, profile_id=profile_id)
    return [ResumeTypeOut.model_validate(r) for r in rows]


@router.post("", response_model=ResumeTypeOut, status_code=201)
async def create_resume_type(
    payload: ResumeTypeCreate,
    user: User = Depends(require_roles(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> ResumeTypeOut:
    row = await service.create_resume_type(db, client_id=user.id, payload=payload)
    return ResumeTypeOut.model_validate(row)


@router.patch("/{resume_type_id}", response_model=ResumeTypeOut)
async def update_resume_type(
    resume_type_id: UUID,
    payload: ResumeTypeUpdate,
    user: User = Depends(require_roles(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> ResumeTypeOut:
    row = await service.get_resume_type_scoped(db, resume_type_id, client_id=user.id)
    row = await service.update_resume_type(db, row, payload)
    return ResumeTypeOut.model_validate(row)


@router.delete("/{resume_type_id}", status_code=204)
async def delete_resume_type(
    resume_type_id: UUID,
    user: User = Depends(require_roles(Role.CLIENT, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user.role == Role.ADMIN:
        row = await service.get_resume_type(db, resume_type_id)
    else:
        row = await service.get_resume_type_scoped(db, resume_type_id, client_id=user.id)
    await service.delete_resume_type(db, row)


@router.post("/{resume_type_id}/resume", response_model=ResumeTypeOut)
async def upload_resume(
    resume_type_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> ResumeTypeOut:
    row = await service.get_resume_type_scoped(db, resume_type_id, client_id=user.id)
    # Read one byte past the limit so an oversized upload is rejected without buffering it all.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    row = await service.upload_resume(db, row, filename=file.filename or "resume", data=data)
    return ResumeTypeOut.model_validate(row)
