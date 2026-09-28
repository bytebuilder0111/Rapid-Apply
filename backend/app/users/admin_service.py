from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.errors import AppError
from app.models import RefreshToken, Role, User
from app.profiles.models import Profile
from app.users.admin_schemas import (
    BidderCreate,
    BidderUpdate,
    ClientCreate,
    ClientUpdate,
    DashboardOut,
    RoleCounts,
)


async def _role_counts(db: AsyncSession, role: Role) -> RoleCounts:
    now = datetime.now(UTC)
    since_7 = now - timedelta(days=7)
    since_30 = now - timedelta(days=30)

    total = await db.scalar(select(func.count()).select_from(User).where(User.role == role))
    last_7 = await db.scalar(
        select(func.count()).select_from(User).where(User.role == role, User.created_at >= since_7)
    )
    last_30 = await db.scalar(
        select(func.count()).select_from(User).where(User.role == role, User.created_at >= since_30)
    )
    return RoleCounts(total=total or 0, last_7_days=last_7 or 0, last_30_days=last_30 or 0)


async def get_dashboard(db: AsyncSession) -> DashboardOut:
    return DashboardOut(
        clients=await _role_counts(db, Role.CLIENT),
        bidders=await _role_counts(db, Role.BIDDER),
    )


async def _username_taken(db: AsyncSession, username: str) -> bool:
    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    return result.scalar_one_or_none() is not None


async def list_clients(
    db: AsyncSession, *, search: str | None, include_deleted: bool
) -> list[User]:
    stmt = select(User).where(User.role == Role.CLIENT)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    if search:
        stmt = stmt.where(User.username.ilike(f"%{search}%") | User.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_client(db: AsyncSession, client_id: UUID) -> User:
    client = await db.get(User, client_id)
    if client is None or client.role != Role.CLIENT:
        raise AppError("not_found", "Client not found", 404)
    return client


async def create_client(db: AsyncSession, payload: ClientCreate) -> User:
    username = payload.username
    if await _username_taken(db, username):
        raise AppError("username_taken", "That username is already taken", 409)

    client = User(
        username=username,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=Role.CLIENT,
        is_active=True,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


async def update_client(db: AsyncSession, client: User, payload: ClientUpdate) -> User:
    data = payload.model_dump(exclude_unset=True)
    if data.get("username"):
        username = data["username"]
        if username.lower() != client.username.lower() and await _username_taken(db, username):
            raise AppError("username_taken", "That username is already taken", 409)
        client.username = username
    if "name" in data and data["name"]:
        client.name = data["name"]
    await db.commit()
    await db.refresh(client)
    return client


async def _revoke_all_refresh_tokens(db: AsyncSession, user_id: UUID) -> None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    for token in result.scalars().all():
        token.revoked = True


async def set_active(db: AsyncSession, user: User, *, is_active: bool) -> User:
    user.is_active = is_active
    if not is_active:
        await _revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    await db.refresh(user)
    return user


async def reset_password(db: AsyncSession, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    await _revoke_all_refresh_tokens(db, user.id)
    await db.commit()


async def soft_delete_client(db: AsyncSession, client: User) -> User:
    client.deleted_at = datetime.now(UTC)
    client.is_active = False
    await _revoke_all_refresh_tokens(db, client.id)

    result = await db.execute(select(User).where(User.client_id == client.id))
    for bidder in result.scalars().all():
        bidder.is_active = False
        await _revoke_all_refresh_tokens(db, bidder.id)

    await db.commit()
    await db.refresh(client)
    return client


async def list_bidders(
    db: AsyncSession, *, client_id: UUID | None, search: str | None
) -> list[User]:
    stmt = select(User).where(User.role == Role.BIDDER)
    if client_id is not None:
        stmt = stmt.where(User.client_id == client_id)
    if search:
        stmt = stmt.where(User.username.ilike(f"%{search}%") | User.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_bidder(db: AsyncSession, bidder_id: UUID) -> User:
    bidder = await db.get(User, bidder_id)
    if bidder is None or bidder.role != Role.BIDDER:
        raise AppError("not_found", "Bidder not found", 404)
    return bidder


async def _validate_profile_for_client(db: AsyncSession, profile_id: UUID, client_id: UUID) -> None:
    profile = await db.get(Profile, profile_id)
    if profile is None or profile.client_id != client_id:
        raise AppError("invalid_profile", "Profile does not belong to this client", 400)


async def create_bidder(db: AsyncSession, payload: BidderCreate) -> User:
    username = payload.username
    if await _username_taken(db, username):
        raise AppError("username_taken", "That username is already taken", 409)

    profile = await db.get(Profile, payload.assigned_profile_id)
    if profile is None:
        raise AppError("invalid_profile", "Profile not found", 400)
    client = await get_client(db, profile.client_id)
    if client.deleted_at is not None:
        raise AppError("client_deleted", "Cannot add a bidder to a deleted client", 400)

    bidder = User(
        username=username,
        name=(payload.name or "").strip() or username,
        password_hash=hash_password(payload.password),
        role=Role.BIDDER,
        is_active=True,
        client_id=client.id,
        assigned_profile_id=payload.assigned_profile_id,
    )
    db.add(bidder)
    await db.commit()
    await db.refresh(bidder)
    return bidder


async def update_bidder(db: AsyncSession, bidder: User, payload: BidderUpdate) -> User:
    data = payload.model_dump(exclude_unset=True)
    if data.get("username"):
        username = data["username"]
        if username.lower() != bidder.username.lower() and await _username_taken(db, username):
            raise AppError("username_taken", "That username is already taken", 409)
        bidder.username = username
    if "name" in data and data["name"]:
        bidder.name = data["name"]
    if "assigned_profile_id" in data and data["assigned_profile_id"]:
        await _validate_profile_for_client(db, data["assigned_profile_id"], bidder.client_id)
        bidder.assigned_profile_id = data["assigned_profile_id"]
    await db.commit()
    await db.refresh(bidder)
    return bidder
