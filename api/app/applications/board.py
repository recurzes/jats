"""What the board reads and edits: the list, one card, a manual fix and a reprint."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.applications.matcher import normalize_company
from app.applications.models import Application, EventSource, StatusEvent
from app.applications.schemas import (
    ApplicationDetail,
    ApplicationPatch,
    ApplicationSummary,
    EmailSummary,
    StatusEventOut,
)
from app.classifier.schema import Status
from app.errors import AppError
from app.gmail.models import Email
from app.printing import queue
from app.printing.models import PrintJob
from app.printing.receipt import render_status_receipt

# The write functions flush but never commit: the router commits.


def _summary_fields(
    application: Application, last_email_subject: str | None, last_email_at: datetime | None
) -> dict[str, object]:
    return {
        "id": application.id,
        "company": application.company,
        "role": application.role,
        "status": application.status,
        "needs_review": application.needs_review,
        "last_event_at": application.last_event_at,
        "last_email_subject": last_email_subject,
        "last_email_at": last_email_at,
    }


def list_applications(
    db: Session,
    user_id: uuid.UUID,
    status: Status | None = None,
    needs_review: bool | None = None,
) -> list[ApplicationSummary]:
    """The user's applications, the most recently changed first."""
    # DISTINCT ON keeps the first row of each application: its newest email.
    last_email = (
        select(Email.application_id, Email.subject, Email.received_at)
        .where(Email.application_id.is_not(None))
        .ext(distinct_on(Email.application_id))
        .order_by(Email.application_id, Email.received_at.desc(), Email.gmail_message_id.desc())
        .subquery()
    )
    query = (
        select(Application, last_email.c.subject, last_email.c.received_at)
        .outerjoin(last_email, last_email.c.application_id == Application.id)
        .where(Application.user_id == user_id)
        .order_by(Application.last_event_at.desc(), Application.id)
    )
    if status is not None:
        query = query.where(Application.status == status)
    if needs_review is not None:
        query = query.where(Application.needs_review.is_(needs_review))
    return [
        ApplicationSummary(**_summary_fields(application, subject, received_at))
        for application, subject, received_at in db.execute(query)
    ]


def _get(db: Session, user_id: uuid.UUID, application_id: uuid.UUID, lock: bool) -> Application:
    query = select(Application).where(
        Application.id == application_id, Application.user_id == user_id
    )
    if lock:
        # Waits for a sync that is changing the same card, and makes it wait for this.
        query = query.with_for_update()
    application = db.scalar(query)
    if application is None:
        raise AppError("NOT_FOUND", "Application not found", 404)
    return application


def _detail(db: Session, application: Application) -> ApplicationDetail:
    emails = db.scalars(
        select(Email)
        .where(Email.application_id == application.id)
        .order_by(Email.received_at.desc(), Email.gmail_message_id.desc())
    ).all()
    events = db.scalars(
        select(StatusEvent)
        .where(StatusEvent.application_id == application.id)
        .order_by(StatusEvent.created_at.desc())
    ).all()
    last_email = emails[0] if emails else None
    return ApplicationDetail(
        **_summary_fields(
            application,
            last_email.subject if last_email else None,
            last_email.received_at if last_email else None,
        ),
        first_seen_at=application.first_seen_at,
        emails=[EmailSummary.model_validate(email) for email in emails],
        status_events=[StatusEventOut.model_validate(event) for event in events],
    )


def get_application(
    db: Session, user_id: uuid.UUID, application_id: uuid.UUID
) -> ApplicationDetail:
    return _detail(db, _get(db, user_id, application_id, lock=False))


def update_application(
    db: Session, user_id: uuid.UUID, application_id: uuid.UUID, changes: ApplicationPatch
) -> ApplicationDetail:
    """Apply a manual fix. A status change is recorded as a manual event and prints nothing."""
    application = _get(db, user_id, application_id, lock=True)
    sent = changes.model_fields_set
    now = datetime.now(UTC)

    if "company" in sent and changes.company is not None:
        application.company = changes.company
        application.company_key = normalize_company(changes.company)
    if "role" in sent:
        application.role = changes.role
    if "status" in sent and changes.status is not None:
        if changes.status != application.status:
            db.add(
                StatusEvent(
                    application_id=application.id,
                    from_status=application.status,
                    to_status=changes.status,
                    source=EventSource.MANUAL,
                    created_at=now,
                )
            )
            application.status = changes.status
            application.last_event_at = now
        # Even an unchanged status clears the flag: the user has confirmed what the AI guessed.
        application.needs_review = False
    if "needs_review" in sent and changes.needs_review is not None:
        application.needs_review = changes.needs_review

    db.flush()
    return _detail(db, application)


def reprint(db: Session, user_id: uuid.UUID, application_id: uuid.UUID) -> PrintJob:
    """Queue another receipt for the application's current status."""
    application = _get(db, user_id, application_id, lock=True)
    latest_event = db.scalar(
        select(StatusEvent)
        .where(StatusEvent.application_id == application.id)
        .order_by(StatusEvent.created_at.desc())
        .limit(1)
    )
    # The email behind the current status. None when the status was set by hand, and then the
    # receipt has no subject and no match line.
    email = db.get(Email, latest_event.email_id) if latest_event and latest_event.email_id else None
    receipt = render_status_receipt(
        company=application.company,
        role=application.role or "",
        status=application.status,
        when=email.received_at if email else application.last_event_at,
        subject=email.subject if email else "",
        confidence=email.confidence if email else None,
    )
    return queue.enqueue_reprint(db, receipt, application.id)
