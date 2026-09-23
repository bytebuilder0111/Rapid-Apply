"""google_connections and sheet_configs tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

google_status_enum = postgresql.ENUM(
    "CONNECTED", "NEEDS_RECONNECT", name="google_connection_status"
)
google_status_column_type = postgresql.ENUM(
    "CONNECTED", "NEEDS_RECONNECT", name="google_connection_status", create_type=False
)


def upgrade() -> None:
    google_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "google_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=2048), nullable=False),
        sa.Column(
            "status", google_status_column_type, nullable=False, server_default="CONNECTED"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_google_connections_client_id", "google_connections", ["client_id"], unique=True
    )

    op.create_table(
        "sheet_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("spreadsheet_id", sa.String(length=255), nullable=True),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_sheet_configs_client_id", "sheet_configs", ["client_id"])
    op.create_index("ix_sheet_configs_profile_id", "sheet_configs", ["profile_id"])
    # One client-level config (user_id NULL) per profile, and one personal config per
    # (profile, bidder) pair. Postgres treats NULLs as distinct in a plain unique index,
    # so each case needs its own partial index rather than a single composite constraint.
    op.create_index(
        "uq_sheet_configs_client_level",
        "sheet_configs",
        ["client_id", "profile_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        "uq_sheet_configs_personal",
        "sheet_configs",
        ["client_id", "profile_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sheet_configs_personal", table_name="sheet_configs")
    op.drop_index("uq_sheet_configs_client_level", table_name="sheet_configs")
    op.drop_index("ix_sheet_configs_profile_id", table_name="sheet_configs")
    op.drop_index("ix_sheet_configs_client_id", table_name="sheet_configs")
    op.drop_table("sheet_configs")

    op.drop_index("ix_google_connections_client_id", table_name="google_connections")
    op.drop_table("google_connections")
    google_status_enum.drop(op.get_bind(), checkfirst=True)
