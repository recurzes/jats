"""Classification in, application out: the status change and the receipt it prints."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.applications.matcher import find_by_company, find_by_thread, normalize_company
from app.applications.models import Application, EventSource, StatusEvent
from app.applications.rules import should_apply
from app.classifier.schema import Classification
from app.config import get_settings
from app.gmail.models import Email, GmailAccount
from app.printing import queue
from app.printing.receipt import render_status_receipt

UNKNOWN_COMPANY = "Unknown"


def apply_classification(
    db: Session, email: Email, classification: Classification
) -> Application | None:
    """Record what the AI said about an email. Returns its application, or None when the email
    is not about a job.

    Flushes but never commits: the caller commits, so the email, the application, the status
    event and the print job are saved in one transaction or not at all.
    """
    now = datetime.now(UTC)
    email.processed_at = now
    if not classification.is_job_related:
        db.flush()
        return None

    status = classification.status
    company_key = normalize_company(classification.company or "")
    application = find_by_thread(db, email.thread_id) or find_by_company(db, company_key)
    if application is None:
        current = None
        application = Application(
            user_id=db.get_one(GmailAccount, email.account_id).user_id,
            company=classification.company or UNKNOWN_COMPANY,
            company_key=company_key,
            role=classification.role,
            status=status,
            thread_id=email.thread_id,
            first_seen_at=email.received_at,
            last_event_at=now,
        )
        db.add(application)
        db.flush()
    else:
        # SELECT ... FOR UPDATE: a manual edit of the same card waits until this is committed.
        db.refresh(application, with_for_update=True)
        current = application.status
        # A later email can name what the first one left out.
        if not application.company_key and company_key:
            application.company = classification.company
            application.company_key = company_key
        application.role = application.role or classification.role
    email.application_id = application.id

    if should_apply(current, status):
        event = StatusEvent(
            application_id=application.id,
            email_id=email.id,
            from_status=current,
            to_status=status,
            source=EventSource.AI,
        )
        db.add(event)
        db.flush()
        application.status = status
        application.last_event_at = now

        unsure = classification.confidence < get_settings().review_threshold
        if unsure or not application.company_key:
            # The event is kept, so the card shows on the board, but nothing is printed.
            application.needs_review = True
        else:
            receipt = render_status_receipt(
                company=application.company,
                role=application.role or "",
                status=status,
                when=email.received_at,
                subject=email.subject,
                confidence=classification.confidence,
            )
            queue.enqueue(db, receipt, status_event_id=event.id)

    db.flush()
    return application
