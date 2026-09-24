"""profiles become resume types: resume summary columns; admin tech stacks removed

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("resume_filename", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("resume_summary", sa.Text(), nullable=True))
    op.add_column(
        "profiles", sa.Column("resume_uploaded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_column("profiles", "tech_stacks")
    # Dropping the table drops its indexes too (their names differ between databases).
    op.drop_table("tech_stacks")


def downgrade() -> None:
    op.create_table(
        "tech_stacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_tech_stacks_name", "tech_stacks", ["name"], unique=True)
    op.add_column(
        "profiles",
        sa.Column(
            "tech_stacks", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"
        ),
    )
    op.drop_column("profiles", "resume_uploaded_at")
    op.drop_column("profiles", "resume_summary")
    op.drop_column("profiles", "resume_filename")
