import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ResumeType(Base):
    """One of a profile's resumes (e.g. Lakeyth Terry's "Java" resume). Only the AI summary
    of the uploaded file is kept, not the file itself; JD matching compares against it."""

    __tablename__ = "resume_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Denormalized from the profile so every query can be scoped by client in one step.
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Every technical skill the uploaded resume names (see RESUME_SYSTEM_PROMPT).
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
