import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AccountState(StrEnum):
    OK = "ok"
    NEEDS_REAUTH = "needs_reauth"


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    email_address: Mapped[str] = mapped_column(String(320))
    # Fernet-encrypted (app.crypto). The refresh token itself is never stored or logged.
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    # Where the next incremental sync starts. Empty until the first sync.
    history_id: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(
        String(16), default=AccountState.OK, server_default=AccountState.OK
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("state IN ('ok', 'needs_reauth')", name="ck_gmail_accounts_state"),
        # One Gmail account per user in V1.
        Index("ix_gmail_accounts_user_id", "user_id", unique=True),
    )
