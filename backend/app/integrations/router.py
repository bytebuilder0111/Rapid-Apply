from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import test_api_key
from app.db import get_db
from app.deps import get_current_user, require_roles
from app.integrations import service
from app.integrations.schemas import OpenAiSettingsOut, SaveApiKeyRequest
from app.models import Role, User

router = APIRouter(dependencies=[Depends(require_roles(Role.CLIENT))])


@router.get("/openai", response_model=OpenAiSettingsOut)
async def get_openai_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> OpenAiSettingsOut:
    return await service.get_settings_out(db, user.id)


@router.put("/openai", response_model=OpenAiSettingsOut)
async def save_openai_settings(
    payload: SaveApiKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OpenAiSettingsOut:
    return await service.save_api_key(
        db, client_id=user.id, api_key=payload.api_key, model=payload.model
    )


@router.delete("/openai", status_code=204)
async def delete_openai_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await service.delete_api_key(db, user.id)


@router.post("/openai/test", status_code=204)
async def test_openai_settings(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    settings_out = await service.get_settings_out(db, user.id)
    api_key = await service.get_decrypted_key_for_client(db, user.id)
    await test_api_key(api_key, settings_out.model)
