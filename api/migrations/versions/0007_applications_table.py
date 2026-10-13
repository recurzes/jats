"""applications table

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-13 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("company_key", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("needs_review", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_event_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('acknowledged', 'replied', 'update', 'rejected')",
            name="ck_applications_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_applications_user_id_status", "applications", ["user_id", "status"], unique=False
    )
    op.create_index("ix_applications_company_key", "applications", ["company_key"], unique=False)

    op.add_column("emails", sa.Column("application_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_emails_application_id", "emails", "applications", ["application_id"], ["id"]
    )
    op.create_index("ix_emails_application_id", "emails", ["application_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_emails_application_id", table_name="emails")
    op.drop_constraint("fk_emails_application_id", "emails", type_="foreignkey")
    op.drop_column("emails", "application_id")

    op.drop_index("ix_applications_company_key", table_name="applications")
    op.drop_index("ix_applications_user_id_status", table_name="applications")
    op.drop_table("applications")
