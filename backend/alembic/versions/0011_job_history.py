"""job_history: jobs a profile applied to before this app, for the duplicate check

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_history",
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
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("position_name", sa.String(length=255), nullable=False),
        sa.Column("job_link", sa.Text(), nullable=True),
        sa.Column("applied_on", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_job_history_client_id", "job_history", ["client_id"])
    op.create_index("ix_job_history_profile_id", "job_history", ["profile_id"])


def downgrade() -> None:
    op.drop_table("job_history")
