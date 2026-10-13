import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Application(Base):
    """One job application: emails feed it, and its status changes are recorded against it."""

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    company: Mapped[str] = mapped_column(Text)
    # The normalized company name that matching compares. Empty while the company is unknown.
    company_key: Mapped[str] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    # Set by a low-confidence result, or one with no company. Such a result is never printed.
    needs_review: Mapped[bool] = mapped_column(default=False, server_default="false")
    # The Gmail thread of the first email.
    thread_id: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('acknowledged', 'replied', 'update', 'rejected')",
            name="ck_applications_status",
        ),
        # The board lists applications by status.
        Index("ix_applications_user_id_status", "user_id", "status"),
        Index("ix_applications_company_key", "company_key"),
    )


class EventSource(StrEnum):
    AI = "ai"
    MANUAL = "manual"


class StatusEvent(Base):
    """One status change of an application."""

    __tablename__ = "status_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    # The email that caused the change. Empty for a manual change.
    email_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("emails.id"))
    # Empty on the event that created the application.
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("source IN ('ai', 'manual')", name="ck_status_events_source"),
        Index("ix_status_events_application_id", "application_id"),
        # One email causes at most one event. Manual events have no email and are unaffected.
        Index(
            "ix_status_events_email_id",
            "email_id",
            unique=True,
            postgresql_where=text("email_id IS NOT NULL"),
        ),
    )
