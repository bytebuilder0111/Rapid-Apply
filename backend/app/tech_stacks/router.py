from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import Role
from app.tech_stacks import service
from app.tech_stacks.schemas import TechStackCreate, TechStackOut, TechStackUpdate

# Any authenticated user (CLIENT/BIDDER building a profile, or ADMIN) can read the
# active list. Only ADMIN can manage it — see admin_router below.
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TechStackOut])
async def list_active_tech_stacks(db: AsyncSession = Depends(get_db)) -> list[TechStackOut]:
    stacks = await service.list_active(db)
    return [TechStackOut.model_validate(s) for s in stacks]


admin_router = APIRouter(dependencies=[Depends(require_roles(Role.ADMIN))])


@admin_router.get("", response_model=list[TechStackOut])
async def list_all_tech_stacks(db: AsyncSession = Depends(get_db)) -> list[TechStackOut]:
    stacks = await service.list_all(db)
    return [TechStackOut.model_validate(s) for s in stacks]


@admin_router.post("", response_model=TechStackOut, status_code=201)
async def create_tech_stack(
    payload: TechStackCreate, db: AsyncSession = Depends(get_db)
) -> TechStackOut:
    stack = await service.create(db, payload)
    return TechStackOut.model_validate(stack)


@admin_router.patch("/{stack_id}", response_model=TechStackOut)
async def update_tech_stack(
    stack_id: UUID, payload: TechStackUpdate, db: AsyncSession = Depends(get_db)
) -> TechStackOut:
    stack = await service.get(db, stack_id)
    stack = await service.update(db, stack, payload)
    return TechStackOut.model_validate(stack)


@admin_router.delete("/{stack_id}", status_code=204)
async def delete_tech_stack(stack_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    stack = await service.get(db, stack_id)
    await service.delete(db, stack)
