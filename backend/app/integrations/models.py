import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AiSettings(Base):
    __tablename__ = "ai_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # Fernet ciphertext (base64), never sent to the browser decrypted — see
    # app/integrations/service.py.
    api_key_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GoogleConnectionStatus(enum.StrEnum):
    CONNECTED = "CONNECTED"
    NEEDS_RECONNECT = "NEEDS_RECONNECT"


class GoogleConnection(Base):
    __tablename__ = "google_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Fernet ciphertext, decrypted only inside app/sheets/writer.py to build short-lived
    # Google credentials — see app/integrations/service.py:encrypt_key/decrypt_key.
    refresh_token_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[GoogleConnectionStatus] = mapped_column(
        Enum(GoogleConnectionStatus, name="google_connection_status"),
        nullable=False,
        default=GoogleConnectionStatus.CONNECTED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
