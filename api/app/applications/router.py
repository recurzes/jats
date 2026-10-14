import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.applications import board
from app.applications.schemas import (
    ApplicationDetail,
    ApplicationPatch,
    ApplicationSummary,
    ReprintQueued,
)
from app.auth.jwt import current_user
from app.classifier.schema import Status
from app.db import get_db
from app.errors import error_responses

router = APIRouter(
    prefix="/applications", tags=["applications"], responses=error_responses(401, 403, 422)
)

User = Annotated[uuid.UUID, Depends(current_user)]
Db = Annotated[Session, Depends(get_db)]


def _blank_is_missing(value: object) -> object:
    # `?status=&needs_review=` means no filter.
    return None if value == "" else value


StatusFilter = Annotated[
    Status | None,
    BeforeValidator(_blank_is_missing),
    Query(description="Only applications with this status."),
]
ReviewFilter = Annotated[
    bool | None,
    BeforeValidator(_blank_is_missing),
    Query(description="Only applications that are, or are not, flagged for review."),
]


@router.get("", summary="List applications")
def list_applications(
    user_id: User, db: Db, status: StatusFilter = None, needs_review: ReviewFilter = None
) -> list[ApplicationSummary]:
    """The board's cards, the most recently changed first."""
    return board.list_applications(db, user_id, status, needs_review)


@router.get("/{application_id}", summary="Get one application", responses=error_responses(404))
def get_application(application_id: uuid.UUID, user_id: User, db: Db) -> ApplicationDetail:
    """One application with its emails and its status history, both newest first."""
    return board.get_application(db, user_id, application_id)


@router.patch(
    "/{application_id}", summary="Fix an application by hand", responses=error_responses(404)
)
def update_application(
    application_id: uuid.UUID, body: ApplicationPatch, user_id: User, db: Db
) -> ApplicationDetail:
    """Change any of `status`, `company`, `role` and `needs_review`.

    A status change is recorded as a manual status event and does not print. Sending a status
    clears `needs_review`, unless the same request sets it.
    """
    application = board.update_application(db, user_id, application_id, body)
    db.commit()
    return application


@router.post(
    "/{application_id}/reprint",
    status_code=201,
    summary="Print the receipt again",
    responses=error_responses(404, 409),
)
def reprint_application(application_id: uuid.UUID, user_id: User, db: Db) -> ReprintQueued:
    """Queue a receipt for the current status. 409 `REPRINT_PENDING` while an earlier reprint of
    this application is still waiting to print."""
    queued = ReprintQueued(job_id=board.reprint(db, user_id, application_id).id)
    db.commit()
    return queued
