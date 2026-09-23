"""ai_settings table (encrypted OpenAI key per client)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("api_key_encrypted", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_settings_client_id", "ai_settings", ["client_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ai_settings_client_id", table_name="ai_settings")
    op.drop_table("ai_settings")
