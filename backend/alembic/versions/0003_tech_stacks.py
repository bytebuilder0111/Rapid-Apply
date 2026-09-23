"""tech_stacks table, seeded with the initial backend stacks

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The stacks that used to be a hardcoded Literal (docs/SPEC.md "AI analysis"); now
# just the seed data for an admin-manageable table.
INITIAL_STACKS = [
    "Python/Django",
    "Node.js/NestJS",
    "Java/Spring",
    "Go",
    ".NET",
    "PHP/Laravel",
    "Ruby/Rails",
]

tech_stacks_table = sa.table(
    "tech_stacks",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
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

    op.bulk_insert(
        tech_stacks_table,
        [{"id": uuid.uuid4(), "name": name, "is_active": True} for name in INITIAL_STACKS],
    )


def downgrade() -> None:
    op.drop_index("ix_tech_stacks_name", table_name="tech_stacks")
    op.drop_table("tech_stacks")
