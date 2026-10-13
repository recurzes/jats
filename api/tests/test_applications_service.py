from datetime import UTC, datetime
from typing import Any

import pytest
from builders import add_account, add_application, add_email, later
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.models import Application, EventSource, StatusEvent
from app.applications.service import apply_classification
from app.classifier.schema import Classification, Status
from app.config import get_settings
from app.gmail.models import Email, GmailAccount
from app.printing.models import JobState, PrintJob
from app.printing.receipt import render_status_receipt


@pytest.fixture
def account(db: Session) -> GmailAccount:
    return add_account(db)


def classification(**fields: Any) -> Classification:
    values = {
        "is_job_related": True,
        "company": "Acme Corp",
        "role": "React Developer",
        "status": "acknowledged",
        "confidence": 0.93,
    }
    return Classification(**(values | fields))


def apply(db: Session, email: Email, **fields: Any) -> Application | None:
    """Apply a classification and commit, as the sync does."""
    application = apply_classification(db, email, classification(**fields))
    db.commit()
    return application


def applications(db: Session) -> list[Application]:
    return list(db.scalars(select(Application).order_by(Application.first_seen_at)))


def events(db: Session) -> list[StatusEvent]:
    return list(db.scalars(select(StatusEvent).order_by(StatusEvent.created_at)))


def jobs(db: Session) -> list[PrintJob]:
    return list(db.scalars(select(PrintJob)))


# --- apply_classification: applications and events


def test_a_job_email_creates_an_application_with_its_first_event(
    db: Session, account: GmailAccount
) -> None:
    email = add_email(db, account, "a")
    before = datetime.now(UTC)

    application = apply(db, email)

    db.expire_all()
    assert [saved.id for saved in applications(db)] == [application.id]
    assert application.user_id == get_settings().owner_user_id
    assert (application.company, application.company_key) == ("Acme Corp", "acme")
    assert application.role == "React Developer"
    assert application.status == Status.ACKNOWLEDGED
    assert application.needs_review is False
    assert application.thread_id == "thread-a"
    assert application.first_seen_at == email.received_at
    assert application.last_event_at >= before
    (event,) = events(db)
    assert (event.application_id, event.email_id) == (application.id, email.id)
    assert (event.from_status, event.to_status) == (None, Status.ACKNOWLEDGED)
    assert event.source == EventSource.AI
    assert email.application_id == application.id
    assert email.processed_at >= before


def test_the_same_status_again_adds_no_event(db: Session, account: GmailAccount) -> None:
    first = apply(db, add_email(db, account, "a"))
    again = add_email(db, account, "b", received_at=later(5))

    second = apply(db, again)

    assert second.id == first.id
    assert len(applications(db)) == 1
    assert len(events(db)) == 1
    assert len(jobs(db)) == 1
    # The email is still linked and done.
    assert again.application_id == first.id
    assert again.processed_at is not None


def test_an_email_that_is_not_about_a_job_is_only_marked_processed(
    db: Session, account: GmailAccount
) -> None:
    email = add_email(db, account, "a")

    result = apply(db, email, is_job_related=False, company=None, role=None, status=None)

    assert result is None
    assert email.processed_at is not None
    assert email.application_id is None
    assert (applications(db), events(db), jobs(db)) == ([], [], [])


def test_a_new_status_moves_the_application(db: Session, account: GmailAccount) -> None:
    application = apply(db, add_email(db, account, "a"))
    first_event_at = application.last_event_at

    apply(db, add_email(db, account, "b", received_at=later(5)), status="rejected")

    db.expire_all()
    assert application.status == Status.REJECTED
    assert application.last_event_at > first_event_at
    assert [(event.from_status, event.to_status) for event in events(db)] == [
        (None, Status.ACKNOWLEDGED),
        (Status.ACKNOWLEDGED, Status.REJECTED),
    ]


def test_a_late_auto_reply_does_not_undo_a_status(db: Session, account: GmailAccount) -> None:
    application = apply(db, add_email(db, account, "a"), status="replied")
    late = add_email(db, account, "b", received_at=later(5))

    apply(db, late, status="acknowledged")

    db.expire_all()
    assert application.status == Status.REPLIED
    assert len(events(db)) == 1
    assert late.application_id == application.id


def test_the_thread_is_matched_before_the_company(db: Session, account: GmailAccount) -> None:
    acme = apply(db, add_email(db, account, "a", thread_id="t1"))
    add_application(db, "Globex")
    reply = add_email(db, account, "b", thread_id="t1", received_at=later(5))

    # The AI read another company name out of the reply.
    matched = apply(db, reply, company="Globex", status="replied")

    assert matched.id == acme.id
    assert matched.company == "Acme Corp"
    assert matched.status == Status.REPLIED


def test_a_new_thread_is_matched_by_company_name(db: Session, account: GmailAccount) -> None:
    acme = apply(db, add_email(db, account, "a"))

    matched = apply(db, add_email(db, account, "b"), company="ACME, Inc.", status="update")

    assert matched.id == acme.id
    assert len(applications(db)) == 1


def test_a_rejected_company_gets_a_new_application(db: Session, account: GmailAccount) -> None:
    rejected = apply(db, add_email(db, account, "a"), status="rejected")

    again = apply(db, add_email(db, account, "b", received_at=later(5)))

    assert again.id != rejected.id
    assert [saved.status for saved in applications(db)] == ["rejected", "acknowledged"]


def test_a_later_email_fills_in_a_missing_role(db: Session, account: GmailAccount) -> None:
    application = apply(db, add_email(db, account, "a"), role=None)

    apply(db, add_email(db, account, "b"), role="Backend Engineer", status="replied")
    apply(db, add_email(db, account, "c"), role="Something Else", status="update")

    db.expire_all()
    assert application.role == "Backend Engineer"


def test_nothing_is_saved_until_the_caller_commits(db: Session, account: GmailAccount) -> None:
    email = add_email(db, account, "a")

    apply_classification(db, email, classification())
    db.rollback()

    assert (applications(db), events(db), jobs(db)) == ([], [], [])
    assert email.processed_at is None
    assert email.application_id is None


# --- apply_classification: the print job


def test_an_applied_event_queues_exactly_one_receipt(db: Session, account: GmailAccount) -> None:
    email = add_email(db, account, "a", subject="Update on your application")

    apply(db, email, status="rejected", confidence=0.87)

    (event,) = events(db)
    (job,) = jobs(db)
    assert job.state == JobState.PENDING
    assert job.status_event_id == event.id
    expected = render_status_receipt(
        company="Acme Corp",
        role="React Developer",
        status="rejected",
        when=email.received_at,
        subject="Update on your application",
        confidence=0.87,
    )
    assert job.payload == expected.model_dump(mode="json", exclude={"id"})
    texts = [line["text"] for line in job.payload["lines"]]
    assert "Acme Corp" in texts
    assert "REJECTED" in texts
    assert "match 87%" in texts


def test_each_status_change_queues_its_own_receipt(db: Session, account: GmailAccount) -> None:
    apply(db, add_email(db, account, "a"))
    apply(db, add_email(db, account, "b", received_at=later(5)), status="replied")
    apply(db, add_email(db, account, "c", received_at=later(9)), status="replied")

    assert len(events(db)) == 2
    assert sorted(job.status_event_id for job in jobs(db)) == sorted(
        event.id for event in events(db)
    )


def test_a_receipt_prints_without_a_role(db: Session, account: GmailAccount) -> None:
    apply(db, add_email(db, account, "a"), role=None)

    (job,) = jobs(db)
    assert not any(line["text"].startswith("Role:") for line in job.payload["lines"])


# --- apply_classification: needs review


def test_a_low_confidence_result_is_flagged_and_not_printed(
    db: Session, account: GmailAccount
) -> None:
    application = apply(db, add_email(db, account, "a"), status="rejected", confidence=0.59)

    assert application.needs_review is True
    assert application.status == Status.REJECTED
    # The event is recorded, so the card shows on the board.
    assert [event.to_status for event in events(db)] == [Status.REJECTED]
    assert jobs(db) == []


def test_a_result_at_the_threshold_is_printed(db: Session, account: GmailAccount) -> None:
    application = apply(db, add_email(db, account, "a"), confidence=0.6)

    assert application.needs_review is False
    assert len(jobs(db)) == 1


def test_a_missing_company_becomes_an_unknown_application(
    db: Session, account: GmailAccount
) -> None:
    application = apply(db, add_email(db, account, "a"), company=None, confidence=0.99)

    assert (application.company, application.company_key) == ("Unknown", "")
    assert application.needs_review is True
    assert len(events(db)) == 1
    assert jobs(db) == []


def test_emails_without_a_company_do_not_share_an_application(
    db: Session, account: GmailAccount
) -> None:
    first = apply(db, add_email(db, account, "a"), company=None)
    second = apply(db, add_email(db, account, "b"), company=None)

    assert first.id != second.id


def test_a_reply_that_names_no_company_still_prints_for_a_known_application(
    db: Session, account: GmailAccount
) -> None:
    application = apply(db, add_email(db, account, "a", thread_id="t1"))
    reply = add_email(db, account, "b", thread_id="t1", received_at=later(5))

    apply(db, reply, company=None, role=None, status="replied")

    assert application.needs_review is False
    assert len(jobs(db)) == 2


def test_a_later_email_names_an_unknown_application(db: Session, account: GmailAccount) -> None:
    application = apply(db, add_email(db, account, "a", thread_id="t1"), company=None)
    reply = add_email(db, account, "b", thread_id="t1", received_at=later(5))

    apply(db, reply, company="Globex", status="replied")

    db.expire_all()
    assert (application.company, application.company_key) == ("Globex", "globex")
    # Still waiting for the review that the first email asked for.
    assert application.needs_review is True
    assert len(jobs(db)) == 1


def test_a_low_confidence_change_flags_an_existing_application(
    db: Session, account: GmailAccount
) -> None:
    application = apply(db, add_email(db, account, "a"))

    apply(db, add_email(db, account, "b", received_at=later(5)), status="rejected", confidence=0.3)

    db.expire_all()
    assert application.status == Status.REJECTED
    assert application.needs_review is True
    assert len(events(db)) == 2
    assert len(jobs(db)) == 1


def test_a_low_confidence_result_that_changes_nothing_does_not_flag(
    db: Session, account: GmailAccount
) -> None:
    application = apply(db, add_email(db, account, "a"))

    apply(db, add_email(db, account, "b", received_at=later(5)), confidence=0.3)

    db.expire_all()
    assert application.needs_review is False
