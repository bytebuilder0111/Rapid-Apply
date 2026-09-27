from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, require_roles, scope_client_id
from app.errors import AppError
from app.models import Role, User
from app.sheets import service
from app.sheets.schemas import SaveSheetConfigRequest, SheetConfigOut, SpreadsheetOut, TabsOut

router = APIRouter(dependencies=[Depends(require_roles(Role.CLIENT, Role.BIDDER))])


def _client_id(user: User) -> UUID:
    client_id = scope_client_id(user)
    assert client_id is not None
    return client_id


def _check_bidder_profile(user: User, profile_id: UUID) -> None:
    if user.role == Role.BIDDER and profile_id != user.assigned_profile_id:
        raise AppError("forbidden", "Not allowed", 403)


@router.get("", response_model=list[SheetConfigOut])
async def list_configs(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SheetConfigOut]:
    client_id = _client_id(user)
    if user.role == Role.BIDDER:
        if user.assigned_profile_id is None:
            return []
        return [await service.get_bidder_config(db, client_id=client_id, user=user)]
    return await service.list_configs_for_client(db, client_id)


@router.get("/spreadsheets", response_model=list[SpreadsheetOut])
async def list_spreadsheets(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SpreadsheetOut]:
    return await service.list_spreadsheets(db, client_id=_client_id(user))


@router.get("/tabs", response_model=TabsOut)
async def list_tabs(
    spreadsheet_id: str = Query(min_length=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TabsOut:
    tabs = await service.list_tabs(db, client_id=_client_id(user), spreadsheet_id=spreadsheet_id)
    return TabsOut(tabs=tabs)


@router.put("/{profile_id}", response_model=SheetConfigOut)
async def save_config(
    profile_id: UUID,
    payload: SaveSheetConfigRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SheetConfigOut:
    _check_bidder_profile(user, profile_id)
    client_id = _client_id(user)
    if user.role == Role.BIDDER:
        return await service.save_bidder_config(db, client_id=client_id, user=user, payload=payload)
    return await service.save_client_config(
        db, client_id=client_id, profile_id=profile_id, payload=payload
    )


@router.delete("/{profile_id}", response_model=SheetConfigOut)
async def clear_config(
    profile_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SheetConfigOut:
    _check_bidder_profile(user, profile_id)
    client_id = _client_id(user)
    if user.role == Role.BIDDER:
        return await service.clear_bidder_config(db, client_id=client_id, user=user)
    return await service.clear_client_config(db, client_id=client_id, profile_id=profile_id)
