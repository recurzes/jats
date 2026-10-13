"""emails table

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-13 20:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("from_domain", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("snippet", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_candidate", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("classification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("classification_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["gmail_accounts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emails_gmail_message_id", "emails", ["gmail_message_id"], unique=True)
    op.create_index("ix_emails_thread_id", "emails", ["thread_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_emails_thread_id", table_name="emails")
    op.drop_index("ix_emails_gmail_message_id", table_name="emails")
    op.drop_table("emails")
