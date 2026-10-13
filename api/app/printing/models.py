import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
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
    # Gets its foreign key and unique index once status_events exists.
    status_event_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'claimed', 'printed', 'failed')", name="ck_print_jobs_state"
        ),
        Index("ix_print_jobs_state_created_at", "state", "created_at"),
    )
