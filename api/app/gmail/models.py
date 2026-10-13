import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
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


class Email(Base):
    """One synced message. The body is never stored: only subject, sender and a snippet."""

    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gmail_accounts.id"))
    gmail_message_id: Mapped[str] = mapped_column(String(64))
    thread_id: Mapped[str] = mapped_column(String(64))
    from_address: Mapped[str] = mapped_column(String(320))
    from_domain: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set by the prefilter: only candidates are worth an AI call.
    is_candidate: Mapped[bool] = mapped_column(default=False, server_default="false")
    classification: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[float | None]
    classification_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The application this email was matched to. Empty for mail that is not about a job.
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", name="fk_emails_application_id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # What stops the same message being written twice.
        Index("ix_emails_gmail_message_id", "gmail_message_id", unique=True),
        Index("ix_emails_thread_id", "thread_id"),
        Index("ix_emails_application_id", "application_id"),
    )


class SyncTrigger(StrEnum):
    SCHEDULE = "schedule"
    MANUAL = "manual"


class SyncResult(StrEnum):
    OK = "ok"
    ERROR = "error"
    FALLBACK_FULL = "fallback_full"
    SKIPPED_LOCKED = "skipped_locked"


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(16))
    # Empty while the sync is still running.
    result: Mapped[str | None] = mapped_column(String(16))
    emails_seen: Mapped[int] = mapped_column(default=0, server_default="0")
    emails_new: Mapped[int] = mapped_column(default=0, server_default="0")
    emails_classified: Mapped[int] = mapped_column(default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("trigger IN ('schedule', 'manual')", name="ck_sync_runs_trigger"),
        CheckConstraint(
            "result IN ('ok', 'error', 'fallback_full', 'skipped_locked')",
            name="ck_sync_runs_result",
        ),
        # GET /status reads the latest run.
        Index("ix_sync_runs_started_at", "started_at"),
    )
