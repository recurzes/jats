"""sync runs table

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-13 20:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column("emails_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("emails_new", sa.Integer(), server_default="0", nullable=False),
        sa.Column("emails_classified", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("trigger IN ('schedule', 'manual')", name="ck_sync_runs_trigger"),
        sa.CheckConstraint(
            "result IN ('ok', 'error', 'fallback_full', 'skipped_locked')",
            name="ck_sync_runs_result",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_started_at", "sync_runs", ["started_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sync_runs_started_at", table_name="sync_runs")
    op.drop_table("sync_runs")
