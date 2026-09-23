from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.tech_stacks.models import TechStack
from app.tech_stacks.schemas import TechStackCreate, TechStackUpdate


async def list_active(db: AsyncSession) -> list[TechStack]:
    result = await db.execute(select(TechStack).where(TechStack.is_active).order_by(TechStack.name))
    return list(result.scalars().all())


async def list_all(db: AsyncSession) -> list[TechStack]:
    result = await db.execute(select(TechStack).order_by(TechStack.name))
    return list(result.scalars().all())


async def get(db: AsyncSession, stack_id: UUID) -> TechStack:
    stack = await db.get(TechStack, stack_id)
    if stack is None:
        raise AppError("not_found", "Tech stack not found", 404)
    return stack


async def _name_conflict(db: AsyncSession, name: str) -> bool:
    result = await db.execute(select(TechStack).where(TechStack.name == name))
    return result.scalar_one_or_none() is not None


async def create(db: AsyncSession, payload: TechStackCreate) -> TechStack:
    if await _name_conflict(db, payload.name):
        raise AppError("name_taken", "A tech stack with this name already exists", 409)
    stack = TechStack(name=payload.name)
    db.add(stack)
    await db.commit()
    await db.refresh(stack)
    return stack


async def update(db: AsyncSession, stack: TechStack, payload: TechStackUpdate) -> TechStack:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] and data["name"] != stack.name:
        if await _name_conflict(db, data["name"]):
            raise AppError("name_taken", "A tech stack with this name already exists", 409)
        stack.name = data["name"]
    if "is_active" in data and data["is_active"] is not None:
        stack.is_active = data["is_active"]
    await db.commit()
    await db.refresh(stack)
    return stack


async def delete(db: AsyncSession, stack: TechStack) -> None:
    await db.delete(stack)
    await db.commit()


async def ensure_active(db: AsyncSession, name: str) -> None:
    result = await db.execute(select(TechStack).where(TechStack.name == name, TechStack.is_active))
    if result.scalar_one_or_none() is None:
        raise AppError("invalid_tech_stack", "This tech stack doesn't exist or is inactive", 400)


async def ensure_all_active(db: AsyncSession, names: list[str]) -> None:
    result = await db.execute(
        select(TechStack.name).where(TechStack.name.in_(names), TechStack.is_active)
    )
    valid_names = set(result.scalars().all())
    invalid = [name for name in names if name not in valid_names]
    if invalid:
        raise AppError(
            "invalid_tech_stack",
            f"These tech stacks don't exist or are inactive: {', '.join(invalid)}",
            400,
        )
