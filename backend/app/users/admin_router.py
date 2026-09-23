from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_roles
from app.models import Role
from app.users import admin_service as service
from app.users.admin_schemas import (
    BidderCreate,
    BidderOut,
    BidderUpdate,
    ClientCreate,
    ClientOut,
    ClientUpdate,
    DashboardOut,
    SetPasswordRequest,
)

router = APIRouter(dependencies=[Depends(require_roles(Role.ADMIN))])


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    return await service.get_dashboard(db)


@router.get("/clients", response_model=list[ClientOut])
async def list_clients(
    search: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> list[ClientOut]:
    clients = await service.list_clients(db, search=search, include_deleted=include_deleted)
    return [ClientOut.model_validate(c) for c in clients]


@router.post("/clients", response_model=ClientOut, status_code=201)
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db)) -> ClientOut:
    client = await service.create_client(db, payload)
    return ClientOut.model_validate(client)


@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientOut:
    client = await service.get_client(db, client_id)
    return ClientOut.model_validate(client)


@router.patch("/clients/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: UUID, payload: ClientUpdate, db: AsyncSession = Depends(get_db)
) -> ClientOut:
    client = await service.get_client(db, client_id)
    client = await service.update_client(db, client, payload)
    return ClientOut.model_validate(client)


@router.post("/clients/{client_id}/deactivate", response_model=ClientOut)
async def deactivate_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientOut:
    client = await service.get_client(db, client_id)
    client = await service.set_active(db, client, is_active=False)
    return ClientOut.model_validate(client)


@router.post("/clients/{client_id}/reactivate", response_model=ClientOut)
async def reactivate_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientOut:
    client = await service.get_client(db, client_id)
    client = await service.set_active(db, client, is_active=True)
    return ClientOut.model_validate(client)


@router.post("/clients/{client_id}/reset-password", status_code=204)
async def reset_client_password(
    client_id: UUID, payload: SetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> None:
    client = await service.get_client(db, client_id)
    await service.reset_password(db, client, payload.new_password)


@router.delete("/clients/{client_id}", response_model=ClientOut)
async def delete_client(client_id: UUID, db: AsyncSession = Depends(get_db)) -> ClientOut:
    client = await service.get_client(db, client_id)
    client = await service.soft_delete_client(db, client)
    return ClientOut.model_validate(client)


@router.get("/bidders", response_model=list[BidderOut])
async def list_bidders(
    client_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[BidderOut]:
    bidders = await service.list_bidders(db, client_id=client_id, search=search)
    return [BidderOut.model_validate(b) for b in bidders]


@router.post("/bidders", response_model=BidderOut, status_code=201)
async def create_bidder(payload: BidderCreate, db: AsyncSession = Depends(get_db)) -> BidderOut:
    bidder = await service.create_bidder(db, payload)
    return BidderOut.model_validate(bidder)


@router.get("/bidders/{bidder_id}", response_model=BidderOut)
async def get_bidder(bidder_id: UUID, db: AsyncSession = Depends(get_db)) -> BidderOut:
    bidder = await service.get_bidder(db, bidder_id)
    return BidderOut.model_validate(bidder)


@router.patch("/bidders/{bidder_id}", response_model=BidderOut)
async def update_bidder(
    bidder_id: UUID, payload: BidderUpdate, db: AsyncSession = Depends(get_db)
) -> BidderOut:
    bidder = await service.get_bidder(db, bidder_id)
    bidder = await service.update_bidder(db, bidder, payload)
    return BidderOut.model_validate(bidder)


@router.post("/bidders/{bidder_id}/deactivate", response_model=BidderOut)
async def deactivate_bidder(bidder_id: UUID, db: AsyncSession = Depends(get_db)) -> BidderOut:
    bidder = await service.get_bidder(db, bidder_id)
    bidder = await service.set_active(db, bidder, is_active=False)
    return BidderOut.model_validate(bidder)


@router.post("/bidders/{bidder_id}/reactivate", response_model=BidderOut)
async def reactivate_bidder(bidder_id: UUID, db: AsyncSession = Depends(get_db)) -> BidderOut:
    bidder = await service.get_bidder(db, bidder_id)
    bidder = await service.set_active(db, bidder, is_active=True)
    return BidderOut.model_validate(bidder)


@router.post("/bidders/{bidder_id}/reset-password", status_code=204)
async def reset_bidder_password(
    bidder_id: UUID, payload: SetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> None:
    bidder = await service.get_bidder(db, bidder_id)
    await service.reset_password(db, bidder, payload.new_password)
