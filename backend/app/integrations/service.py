from functools import lru_cache
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.integrations.models import AiSettings
from app.integrations.schemas import OpenAiSettingsOut


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise AppError(
            "encryption_not_configured",
            "Server is missing ENCRYPTION_KEY; ask an administrator to configure it",
            500,
        )
    try:
        return Fernet(settings.encryption_key.encode())
    except (ValueError, TypeError) as exc:
        raise AppError(
            "encryption_not_configured",
            "Server's ENCRYPTION_KEY is invalid; ask an administrator to fix it",
            500,
        ) from exc


def encrypt_key(plain_key: str) -> str:
    return _fernet().encrypt(plain_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    try:
        return _fernet().decrypt(encrypted_key.encode()).decode()
    except InvalidToken as exc:
        raise AppError("decryption_failed", "Stored API key could not be decrypted", 500) from exc


def mask_key(plain_key: str) -> str:
    if len(plain_key) <= 7:
        return "***"
    return f"{plain_key[:3]}...{plain_key[-4:]}"


async def get_settings_row(db: AsyncSession, client_id: UUID) -> AiSettings | None:
    result = await db.execute(select(AiSettings).where(AiSettings.client_id == client_id))
    return result.scalar_one_or_none()


async def get_settings_out(db: AsyncSession, client_id: UUID) -> OpenAiSettingsOut:
    row = await get_settings_row(db, client_id)
    if row is None:
        return OpenAiSettingsOut(has_key=False, masked_key=None, model=settings.default_ai_model)
    return OpenAiSettingsOut(
        has_key=True, masked_key=mask_key(decrypt_key(row.api_key_encrypted)), model=row.model
    )


async def save_api_key(
    db: AsyncSession, *, client_id: UUID, api_key: str, model: str | None
) -> OpenAiSettingsOut:
    row = await get_settings_row(db, client_id)
    resolved_model = model or (row.model if row else settings.default_ai_model)
    encrypted = encrypt_key(api_key)
    if row is None:
        row = AiSettings(
            client_id=client_id,
            provider="openai",
            model=resolved_model,
            api_key_encrypted=encrypted,
        )
        db.add(row)
    else:
        row.model = resolved_model
        row.api_key_encrypted = encrypted
    await db.commit()
    return OpenAiSettingsOut(has_key=True, masked_key=mask_key(api_key), model=resolved_model)


async def delete_api_key(db: AsyncSession, client_id: UUID) -> None:
    row = await get_settings_row(db, client_id)
    if row is not None:
        await db.delete(row)
        await db.commit()


async def get_decrypted_key_for_client(db: AsyncSession, client_id: UUID) -> str:
    row = await get_settings_row(db, client_id)
    if row is None:
        raise AppError("no_api_key", "No OpenAI API key configured for this client", 400)
    return decrypt_key(row.api_key_encrypted)
