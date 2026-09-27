"""sheet_configs.spreadsheet_name (display name of the chosen spreadsheet)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sheet_configs", sa.Column("spreadsheet_name", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sheet_configs", "spreadsheet_name")
