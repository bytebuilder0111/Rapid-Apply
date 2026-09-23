"""analyses table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

record_status_enum = postgresql.ENUM(
    "PENDING", "SUCCESS", "FAILED", "SKIPPED", name="record_status"
)
record_status_column_type = postgresql.ENUM(
    "PENDING", "SUCCESS", "FAILED", "SKIPPED", name="record_status", create_type=False
)


def upgrade() -> None:
    record_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("position_name", sa.String(length=255), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("jd_hash", sa.String(length=64), nullable=False),
        sa.Column("job_link", sa.String(length=2048), nullable=True),
        sa.Column(
            "recommended_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "selected_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "record_status",
            record_status_column_type,
            nullable=False,
            server_default="SKIPPED",
        ),
        sa.Column("record_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("record_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_analyses_client_id", "analyses", ["client_id"])
    op.create_index("ix_analyses_jd_hash", "analyses", ["jd_hash"])
    op.create_index("ix_analyses_client_id_created_at", "analyses", ["client_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_analyses_client_id_created_at", table_name="analyses")
    op.drop_index("ix_analyses_jd_hash", table_name="analyses")
    op.drop_index("ix_analyses_client_id", table_name="analyses")
    op.drop_table("analyses")
    record_status_enum.drop(op.get_bind(), checkfirst=True)
