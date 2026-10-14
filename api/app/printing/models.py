import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    name: Mapped[str] = mapped_column(String(100))
    # SHA-256 hex of the device key. The key itself is never stored.
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_devices_key_hash", "key_hash", unique=True),)


class JobState(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PRINTED = "printed"
    FAILED = "failed"


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # The device that last claimed the job.
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id"))
    # Receipt lines and the cut flag, without the job id.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(
        String(16), default=JobState.PENDING, server_default=JobState.PENDING
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(100))
    # The status change this receipt is for. Empty for test jobs and reprints.
    status_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("status_events.id", name="fk_print_jobs_status_event_id")
    )
    # The application a reprint is for. Empty for every other job.
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id", name="fk_print_jobs_application_id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'claimed', 'printed', 'failed')", name="ck_print_jobs_state"
        ),
        Index("ix_print_jobs_state_created_at", "state", "created_at"),
        # One status event creates at most one print job. Reprints have no event.
        Index(
            "ix_print_jobs_status_event_id",
            "status_event_id",
            unique=True,
            postgresql_where=text("status_event_id IS NOT NULL"),
        ),
        Index(
            "ix_print_jobs_application_id",
            "application_id",
            postgresql_where=text("application_id IS NOT NULL"),
        ),
    )
