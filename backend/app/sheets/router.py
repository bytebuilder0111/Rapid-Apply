from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, require_roles, scope_client_id
from app.errors import AppError
from app.models import Role, User
from app.sheets import service
from app.sheets.schemas import SaveSheetConfigRequest, SheetConfigOut, TabsOut, TestWriteRequest

router = APIRouter(dependencies=[Depends(require_roles(Role.CLIENT, Role.BIDDER))])


@router.get("", response_model=list[SheetConfigOut])
async def list_configs(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SheetConfigOut]:
    client_id = scope_client_id(user)
    assert client_id is not None
    if user.role == Role.BIDDER:
        if user.assigned_profile_id is None:
            return []
        return [await service.get_bidder_config(db, client_id=client_id, user=user)]
    return await service.list_configs_for_client(db, client_id)


@router.put("/{profile_id}", response_model=SheetConfigOut)
async def save_config(
    profile_id: UUID,
    payload: SaveSheetConfigRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SheetConfigOut:
    client_id = scope_client_id(user)
    assert client_id is not None
    if user.role == Role.BIDDER:
        if profile_id != user.assigned_profile_id:
            raise AppError("forbidden", "Not allowed", 403)
        return await service.save_bidder_config(db, client_id=client_id, user=user, payload=payload)
    return await service.save_client_config(
        db, client_id=client_id, profile_id=profile_id, payload=payload
    )


@router.get("/tabs", response_model=TabsOut)
async def list_tabs(
    spreadsheet: str = Query(min_length=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TabsOut:
    client_id = scope_client_id(user)
    assert client_id is not None
    tabs = await service.list_tabs(db, client_id=client_id, spreadsheet=spreadsheet)
    return TabsOut(tabs=tabs)


@router.post("/test", status_code=204)
async def test_write(
    payload: TestWriteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    client_id = scope_client_id(user)
    assert client_id is not None
    await service.test_write(
        db, client_id=client_id, spreadsheet=payload.spreadsheet, sheet_name=payload.sheet_name
    )
