from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import test_api_key
from app.config import settings
from app.db import get_db
from app.deps import get_current_user, require_roles, scope_client_id
from app.integrations import google_service, service
from app.integrations.schemas import (
    GoogleAuthorizeUrlOut,
    GoogleConnectionOut,
    OpenAiSettingsOut,
    SaveApiKeyRequest,
)
from app.models import Role, User

router = APIRouter()


@router.get(
    "/openai", response_model=OpenAiSettingsOut, dependencies=[Depends(require_roles(Role.CLIENT))]
)
async def get_openai_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> OpenAiSettingsOut:
    return await service.get_settings_out(db, user.id)


@router.put(
    "/openai", response_model=OpenAiSettingsOut, dependencies=[Depends(require_roles(Role.CLIENT))]
)
async def save_openai_settings(
    payload: SaveApiKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OpenAiSettingsOut:
    return await service.save_api_key(
        db, client_id=user.id, api_key=payload.api_key, model=payload.model
    )


@router.delete("/openai", status_code=204, dependencies=[Depends(require_roles(Role.CLIENT))])
async def delete_openai_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.delete_api_key(db, user.id)


@router.post("/openai/test", status_code=204, dependencies=[Depends(require_roles(Role.CLIENT))])
async def test_openai_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    settings_out = await service.get_settings_out(db, user.id)
    api_key = await service.get_decrypted_key_for_client(db, user.id)
    await test_api_key(api_key, settings_out.model)


@router.get(
    "/google/authorize",
    response_model=GoogleAuthorizeUrlOut,
    dependencies=[Depends(require_roles(Role.CLIENT))],
)
async def google_authorize(user: User = Depends(get_current_user)) -> GoogleAuthorizeUrlOut:
    return GoogleAuthorizeUrlOut(authorize_url=google_service.build_authorize_url(user.id))


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    code: str = Query(...), state: str = Query(...), db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    # Hit directly by Google's redirect, so there's no bearer token here — the signed
    # `state` (see google_service._sign_state) is what identifies the client.
    try:
        await google_service.handle_callback(db, code=code, state=state)
        return RedirectResponse(f"{settings.frontend_url}/client/integrations?google=connected")
    except Exception:
        return RedirectResponse(f"{settings.frontend_url}/client/integrations?google=error")


@router.get(
    "/google",
    response_model=GoogleConnectionOut,
    dependencies=[Depends(require_roles(Role.CLIENT, Role.BIDDER))],
)
async def get_google_connection(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> GoogleConnectionOut:
    client_id = scope_client_id(user)
    assert client_id is not None
    return await google_service.get_connection_out(db, client_id)


@router.delete("/google", status_code=204, dependencies=[Depends(require_roles(Role.CLIENT))])
async def disconnect_google(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await google_service.disconnect(db, user.id)
