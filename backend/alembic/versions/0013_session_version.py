"""users get a session version, so ending a user's sessions takes effect at once

Every access token carries the user's session_version; bumping it (password reset,
deactivation, or the admin's "Sign out") makes all of that user's tokens invalid immediately
instead of when they expire.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
