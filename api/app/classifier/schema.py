from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator


class Status(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    REPLIED = "replied"
    UPDATE = "update"
    REJECTED = "rejected"


class Classification(BaseModel):
    """What the AI says about one email. Every AI response is validated against this."""

    is_job_related: bool
    company: str | None = None
    role: str | None = None
    status: Status | None = None
    confidence: float = Field(ge=0, le=1)

    @field_validator("company", "role", "status", mode="before")
    @classmethod
    def _blank_is_missing(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _status_in_lower_case(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _job_emails_have_a_status(self) -> Self:
        if self.is_job_related and self.status is None:
            raise ValueError("status is required when is_job_related is true")
        return self
