import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.applications.models import EventSource
from app.classifier.schema import Status


class ApplicationSummary(BaseModel):
    """One card on the board."""

    id: uuid.UUID
    company: str
    role: str | None
    status: Status
    needs_review: bool
    last_event_at: datetime
    # Empty for an application that has no email.
    last_email_subject: str | None
    last_email_at: datetime | None


class EmailSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    from_address: str
    snippet: str
    received_at: datetime


class StatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Empty on the event that created the application.
    from_status: Status | None
    to_status: Status
    source: EventSource
    # The email that caused the change. Empty for a manual change.
    email_id: uuid.UUID | None
    created_at: datetime


class ApplicationDetail(ApplicationSummary):
    """One card with what the detail panel shows. Emails and events are newest first."""

    first_seen_at: datetime
    emails: list[EmailSummary]
    status_events: list[StatusEventOut]


class ApplicationPatch(BaseModel):
    """A manual fix. Only the fields that are sent change."""

    status: Status | None = None
    company: str | None = Field(default=None, min_length=1, max_length=200)
    # null clears the role.
    role: str | None = Field(default=None, max_length=200)
    needs_review: bool | None = None

    @field_validator("company", "role", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("role")
    @classmethod
    def _blank_role_is_missing(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def _only_the_role_can_be_cleared(self) -> Self:
        for name in ("status", "company", "needs_review"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ReprintQueued(BaseModel):
    job_id: uuid.UUID
