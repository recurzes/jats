"""gmail accounts table

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13 18:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "gmail_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("history_id", sa.String(length=32), nullable=True),
        sa.Column("state", sa.String(length=16), server_default="ok", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("state IN ('ok', 'needs_reauth')", name="ck_gmail_accounts_state"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gmail_accounts_user_id", "gmail_accounts", ["user_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_gmail_accounts_user_id", table_name="gmail_accounts")
    op.drop_table("gmail_accounts")
