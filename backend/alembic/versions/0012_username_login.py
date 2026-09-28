"""users log in with a username instead of an email

The email column becomes username. Existing accounts get their display name as username
(e.g. "Max", "Admin"). Uniqueness is case-insensitive.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.alter_column("users", "email", new_column_name="username", type_=sa.String(length=50))
    conn = op.get_bind()
    # Name -> username; a numeric suffix keeps them unique if two accounts share a name.
    conn.execute(
        sa.text(
            "UPDATE users u SET username = regexp_replace(u.name, '[^A-Za-z0-9._-]', '', 'g') "
            "|| CASE WHEN r.n > 1 THEN r.n::text ELSE '' END "
            "FROM (SELECT id, row_number() OVER (PARTITION BY lower(name) ORDER BY created_at) "
            "AS n FROM users) r WHERE r.id = u.id"
        )
    )
    op.create_index("ix_users_username_lower", "users", [sa.text("lower(username)")], unique=True)


def downgrade() -> None:
    raise NotImplementedError(
        "0012 replaced email addresses with usernames; the old emails can't be restored."
    )
