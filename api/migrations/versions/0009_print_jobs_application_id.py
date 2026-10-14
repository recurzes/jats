"""print jobs application id

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-14 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("print_jobs", sa.Column("application_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_print_jobs_application_id", "print_jobs", "applications", ["application_id"], ["id"]
    )
    op.create_index(
        "ix_print_jobs_application_id",
        "print_jobs",
        ["application_id"],
        unique=False,
        postgresql_where=sa.text("application_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_print_jobs_application_id", table_name="print_jobs")
    op.drop_constraint("fk_print_jobs_application_id", "print_jobs", type_="foreignkey")
    op.drop_column("print_jobs", "application_id")
