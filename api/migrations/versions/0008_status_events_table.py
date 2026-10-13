"""status events table

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13 22:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=True),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('ai', 'manual')", name="ck_status_events_source"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_status_events_application_id", "status_events", ["application_id"], unique=False
    )
    op.create_index(
        "ix_status_events_email_id",
        "status_events",
        ["email_id"],
        unique=True,
        postgresql_where=sa.text("email_id IS NOT NULL"),
    )

    op.create_foreign_key(
        "fk_print_jobs_status_event_id",
        "print_jobs",
        "status_events",
        ["status_event_id"],
        ["id"],
    )
    op.create_index(
        "ix_print_jobs_status_event_id",
        "print_jobs",
        ["status_event_id"],
        unique=True,
        postgresql_where=sa.text("status_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_print_jobs_status_event_id", table_name="print_jobs")
    op.drop_constraint("fk_print_jobs_status_event_id", "print_jobs", type_="foreignkey")

    op.drop_index("ix_status_events_email_id", table_name="status_events")
    op.drop_index("ix_status_events_application_id", table_name="status_events")
    op.drop_table("status_events")
