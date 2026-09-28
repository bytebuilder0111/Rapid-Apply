"""split resume types out of profiles: a profile is a person that owns resume types

Before: each `profiles` row was one resume (Java, Node, ...).
After:  `profiles` rows are people (e.g. "Lakeyth Terry"); their resumes live in
        `resume_types`. Each client's existing rows move under one new profile, keeping their
        ids, so nothing that pointed at a resume is lost. Bidder assignments, sheet configs and
        analyses are re-pointed at the new profile.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-27

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MIGRATED_PROFILE_NAME = "Default profile"


def upgrade() -> None:
    op.create_table(
        "resume_types",
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
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("resume_filename", sa.String(length=255), nullable=True),
        sa.Column("resume_summary", sa.Text(), nullable=True),
        sa.Column("resume_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_resume_types_client_id", "resume_types", ["client_id"])
    op.create_index("ix_resume_types_profile_id", "resume_types", ["profile_id"])

    op.add_column(
        "analyses",
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    for column in ("recommended_resume_type_id", "selected_resume_type_id"):
        op.add_column(
            "analyses",
            sa.Column(
                column,
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("resume_types.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    conn = op.get_bind()
    client_ids = [
        row[0] for row in conn.execute(sa.text("SELECT DISTINCT client_id FROM profiles"))
    ]
    for client_id in client_ids:
        person_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO profiles (id, client_id, name, skills, is_active, created_at, "
                "updated_at) VALUES (:person, :client, :name, '{}', true, now(), now())"
            ),
            {"person": person_id, "client": client_id, "name": MIGRATED_PROFILE_NAME},
        )
        # Every existing row becomes a resume type (same id) under the new person profile.
        conn.execute(
            sa.text(
                "INSERT INTO resume_types (id, client_id, profile_id, name, skills, "
                "resume_filename, resume_summary, resume_uploaded_at, is_active, created_at, "
                "updated_at) "
                "SELECT id, client_id, :person, name, skills, resume_filename, resume_summary, "
                "resume_uploaded_at, is_active, created_at, updated_at "
                "FROM profiles WHERE client_id = :client AND id <> :person"
            ),
            {"person": person_id, "client": client_id},
        )
        conn.execute(
            sa.text(
                "UPDATE analyses SET profile_id = :person, "
                "recommended_resume_type_id = recommended_profile_id, "
                "selected_resume_type_id = selected_profile_id "
                "WHERE client_id = :client"
            ),
            {"person": person_id, "client": client_id},
        )
        conn.execute(
            sa.text(
                "UPDATE users SET assigned_profile_id = :person "
                "WHERE client_id = :client AND assigned_profile_id IS NOT NULL"
            ),
            {"person": person_id, "client": client_id},
        )

    # Sheet configs were per resume; they're per person now. Keep the most recently updated
    # one per (client, bidder-or-client-level) and point it at the new person profile.
    conn.execute(
        sa.text(
            "DELETE FROM sheet_configs sc USING sheet_configs newer "
            "WHERE sc.client_id = newer.client_id "
            "AND sc.user_id IS NOT DISTINCT FROM newer.user_id "
            "AND (sc.updated_at, sc.id) < (newer.updated_at, newer.id)"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE sheet_configs sc SET profile_id = rt.profile_id "
            "FROM resume_types rt WHERE rt.id = sc.profile_id"
        )
    )

    # In stored results, the recommended id now refers to a resume type.
    conn.execute(
        sa.text(
            "UPDATE analyses SET result = (result - 'recommended_profile_id') || "
            "jsonb_build_object('recommended_resume_type_id', result->'recommended_profile_id') "
            "WHERE result->'recommended_profile_id' IS NOT NULL"
        )
    )

    op.drop_column("analyses", "recommended_profile_id")
    op.drop_column("analyses", "selected_profile_id")
    conn.execute(sa.text("DELETE FROM profiles WHERE id IN (SELECT id FROM resume_types)"))
    for column in ("skills", "resume_filename", "resume_summary", "resume_uploaded_at"):
        op.drop_column("profiles", column)


def downgrade() -> None:
    raise NotImplementedError(
        "0010 merges resume-level sheet configs into one per profile, so it can't be undone "
        "automatically. Restore from a database backup instead."
    )
