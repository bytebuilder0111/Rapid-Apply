"""profiles.primary_backend_skill -> profiles.tech_stacks (multi-select)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("tech_stacks", postgresql.ARRAY(sa.String()), nullable=True),
    )
    # Preserve existing single-value data as a one-element array.
    op.execute(
        "UPDATE profiles SET tech_stacks = ARRAY[primary_backend_skill] "
        "WHERE primary_backend_skill IS NOT NULL"
    )
    op.alter_column(
        "profiles", "tech_stacks", nullable=False, server_default="{}"
    )
    op.drop_column("profiles", "primary_backend_skill")


def downgrade() -> None:
    op.add_column(
        "profiles", sa.Column("primary_backend_skill", sa.String(length=255), nullable=True)
    )
    op.execute("UPDATE profiles SET primary_backend_skill = tech_stacks[1]")
    op.alter_column("profiles", "primary_backend_skill", nullable=False)
    op.drop_column("profiles", "tech_stacks")
