"""The whole loop with a fake Gmail and a fake AI: sync, prefilter, classify, apply, print."""

import logging

import pytest
from builders import add_account
from gmail_fake import FakeGmail, added, mail, message
from llm_fake import answer, status_error, use_llm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications import service
from app.applications.models import Application, StatusEvent
from app.classifier.schema import Status
from app.config import get_settings
from app.gmail import sync
from app.gmail.models import Email, GmailAccount, SyncResult, SyncRun, SyncTrigger
from app.gmail.sync import run_sync
from app.printing.models import JobState, PrintJob

MALFORMED = "Sure! Here is the classification: rejected"
NOT_A_JOB = answer(is_job_related=False, company=None, role=None, status=None)

ACME = "Acme Corp Careers <careers@acme.example>"
REJECTION = "Unfortunately we are moving forward with other candidates"


@pytest.fixture
def account(db: Session) -> GmailAccount:
    return add_account(db)


@pytest.fixture(autouse=True)
def classification_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """conftest.py turns classification off for every other test."""
    monkeypatch.setattr(get_settings(), "max_classifications_per_run", 30)


@pytest.fixture
def use_gmail(monkeypatch: pytest.MonkeyPatch):
    """Make the sync talk to this fake instead of building a real Gmail service."""

    def use(gmail: FakeGmail) -> FakeGmail:
        monkeypatch.setattr(sync, "get_gmail_service", lambda account: gmail)
        return gmail

    return use


def arrive(gmail: FakeGmail, *messages: dict) -> None:
    """Deliver new mail: the next sync hears about it from the history listing."""
    for item in messages:
        gmail.stored[item["id"]] = item
    ids = [item["id"] for item in messages]
    gmail.history_pages = [{"history": [added(*ids)], "historyId": "200"}]


def sync_once(db: Session, account: GmailAccount) -> SyncRun:
    return run_sync(db, account, SyncTrigger.SCHEDULE)


def emails(db: Session) -> list[Email]:
    return list(db.scalars(select(Email).order_by(Email.received_at, Email.gmail_message_id)))


def applications(db: Session) -> list[Application]:
    return list(db.scalars(select(Application).order_by(Application.first_seen_at)))


def events(db: Session) -> list[StatusEvent]:
    return list(db.scalars(select(StatusEvent).order_by(StatusEvent.created_at)))


def jobs(db: Session) -> list[PrintJob]:
    return list(db.scalars(select(PrintJob)))


# --- sync, classify, apply


def test_one_sync_produces_an_application_and_a_print_job(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gmail(FakeGmail(messages=[message("a")]))
    llm = use_llm(monkeypatch, answer())

    run = sync_once(db, account)

    assert run.result == SyncResult.OK
    assert (run.emails_seen, run.emails_new, run.emails_classified) == (1, 1, 1)
    (application,) = applications(db)
    assert (application.company, application.status) == ("Acme Corp", Status.ACKNOWLEDGED)
    (email,) = emails(db)
    assert email.application_id == application.id
    assert email.classification["status"] == "acknowledged"
    assert email.processed_at is not None
    (event,) = events(db)
    (job,) = jobs(db)
    assert (job.state, job.status_event_id) == (JobState.PENDING, event.id)
    # The AI was given the body, which is stored nowhere.
    assert "Thank you for applying to the React Developer position" in llm.user_messages()[0]


def test_only_candidates_are_sent_to_the_ai(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    newsletter = mail("a", "News <news@shop.example>", "This week's deals")
    use_gmail(FakeGmail(messages=[newsletter, message("b")]))
    llm = use_llm(monkeypatch, NOT_A_JOB)

    run = sync_once(db, account)

    assert (run.emails_new, run.emails_classified) == (2, 1)
    assert len(llm.calls) == 1
    skipped, classified = emails(db)
    assert (skipped.is_candidate, skipped.processed_at) == (False, None)
    # Classified as not about a job: done, and no application.
    assert classified.processed_at is not None
    assert classified.classification["is_job_related"] is False
    assert applications(db) == []


def test_one_bad_email_does_not_block_the_others(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gmail(FakeGmail(messages=[mail("a", ACME, REJECTION), mail("b", ACME, REJECTION, None, 5)]))
    use_llm(monkeypatch, answer(), answer(company="Globex"))
    apply = service.apply_classification

    def explode_on_the_first(db: Session, email: Email, classification):
        if email.gmail_message_id == "a":
            raise RuntimeError("boom")
        return apply(db, email, classification)

    monkeypatch.setattr(sync, "apply_classification", explode_on_the_first)

    run = sync_once(db, account)

    assert run.result == SyncResult.OK
    assert run.emails_classified == 1
    bad, good = emails(db)
    # Nothing of the failed email was kept, except that it was tried.
    assert (bad.classification, bad.processed_at, bad.application_id) == (None, None, None)
    assert bad.classification_attempts == 1
    assert good.processed_at is not None
    assert [application.company for application in applications(db)] == ["Globex"]


def test_a_provider_outage_fails_the_run_and_the_next_one_catches_up(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = use_gmail(FakeGmail(messages=[message("a"), message("b")]))
    llm = use_llm(monkeypatch, status_error(503), status_error(503))

    run = sync_once(db, account)

    assert run.result == SyncResult.ERROR
    assert run.error == "The AI provider is unavailable (503)"
    assert (run.emails_new, run.emails_classified) == (2, 0)
    # The second email was not tried: the provider is down for all of them.
    assert len(llm.calls) == 2
    # The emails are stored and the bookmark moved, and an outage counts no attempt.
    assert account.history_id == "100"
    assert [(email.processed_at, email.classification_attempts) for email in emails(db)] == [
        (None, 0),
        (None, 0),
    ]

    use_llm(monkeypatch, answer(), answer())
    retry = sync_once(db, account)

    assert (retry.result, retry.emails_new, retry.emails_classified) == (SyncResult.OK, 0, 2)
    assert all(email.processed_at for email in emails(db))
    # The bodies were read from Gmail again.
    assert [call["id"] for call in gmail.called("messages.get")] == ["a", "b", "a", "b"]


def test_a_reply_from_a_personal_address_in_a_known_thread_is_classified(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = use_gmail(FakeGmail(messages=[mail("a", ACME, "Your application", "t1")]))
    use_llm(monkeypatch, answer())
    sync_once(db, account)

    arrive(gmail, mail("b", "Jane <jane@gmail.com>", "Re: quick chat?", "t1", 60))
    use_llm(monkeypatch, answer(status="replied", company=None, role=None))
    run = sync_once(db, account)

    assert run.emails_classified == 1
    assert emails(db)[1].is_candidate is True
    (application,) = applications(db)
    assert application.status == Status.REPLIED


def test_a_reply_in_the_same_sync_as_the_first_email_is_classified_too(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gmail(
        FakeGmail(
            messages=[
                mail("a", ACME, "Your application", "t1"),
                mail("b", "Jane <jane@gmail.com>", "Re: quick chat?", "t1", 60),
                mail("c", "Jane <jane@gmail.com>", "Lunch?", "t9", 90),
            ]
        )
    )
    llm = use_llm(monkeypatch, answer(), answer(status="replied", company=None, role=None))

    run = sync_once(db, account)

    # When "b" was stored its thread had no application yet.
    assert run.emails_classified == 2
    assert len(llm.calls) == 2
    assert [email.is_candidate for email in emails(db)] == [True, True, False]
    (application,) = applications(db)
    assert application.status == Status.REPLIED


# --- retries


def test_a_failing_email_is_retried_twice_then_given_up_on(
    db: Session,
    account: GmailAccount,
    use_gmail,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    gmail = use_gmail(FakeGmail(messages=[message("a")]))
    # Every AI call is asked once more by the classifier itself, so each sync uses two answers.
    llm = use_llm(monkeypatch, *[MALFORMED] * 6)

    first = sync_once(db, account)
    (email,) = emails(db)
    assert (first.result, first.emails_classified) == (SyncResult.OK, 0)
    assert (email.classification_attempts, email.processed_at) == (1, None)

    sync_once(db, account)
    assert (email.classification_attempts, email.processed_at) == (2, None)
    assert email.classification is None

    with caplog.at_level(logging.WARNING, logger="app.gmail.sync"):
        sync_once(db, account)

    assert email.classification_attempts == 3
    assert email.processed_at is not None
    assert email.classification == {"error": "Invalid AI answer: not a JSON object"}
    assert email.application_id is None
    given_up = "Gave up classifying an email"
    (warning,) = [record for record in caplog.records if record.getMessage() == given_up]
    assert warning.levelno == logging.WARNING
    assert warning.data == {
        "gmail_message_id": "a",
        "attempts": 3,
        "reason": "Invalid AI answer: not a JSON object",
    }

    # Given up on: no more AI calls, and no more Gmail fetches.
    sync_once(db, account)
    assert len(llm.calls) == 6
    # The first sync fetched the message; each retry fetched its body again.
    assert [call["id"] for call in gmail.called("messages.get")] == ["a", "a", "a"]
    assert applications(db) == []


def test_a_retry_that_succeeds_is_applied(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gmail(FakeGmail(messages=[message("a")]))
    use_llm(monkeypatch, MALFORMED, MALFORMED, answer(status="rejected"))

    sync_once(db, account)
    run = sync_once(db, account)

    assert run.emails_classified == 1
    (email,) = emails(db)
    assert email.classification_attempts == 1
    assert [application.status for application in applications(db)] == [Status.REJECTED]
    assert len(jobs(db)) == 1


def test_an_email_deleted_before_its_retry_is_given_up_on(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = use_gmail(FakeGmail(messages=[message("a")]))
    llm = use_llm(monkeypatch, MALFORMED, MALFORMED)
    sync_once(db, account)
    del gmail.stored["a"]

    run = sync_once(db, account)

    assert run.result == SyncResult.OK
    (email,) = emails(db)
    assert email.processed_at is not None
    assert email.classification == {"error": "The message no longer exists in Gmail"}
    assert len(llm.calls) == 2


# --- the cap


def test_a_run_classifies_at_most_the_cap_and_the_next_run_does_the_rest(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    inbox = [mail(f"m{number:02}", ACME, "Your application", None, number) for number in range(50)]
    gmail = use_gmail(FakeGmail(messages=inbox))
    llm = use_llm(monkeypatch, *[answer()] * 50)

    first = sync_once(db, account)

    assert (first.result, first.emails_new, first.emails_classified) == (SyncResult.OK, 50, 30)
    assert len(llm.calls) == 30
    # The oldest 30 are done.
    assert [email.processed_at is not None for email in emails(db)] == [True] * 30 + [False] * 20

    second = sync_once(db, account)

    assert (second.emails_new, second.emails_classified) == (0, 20)
    assert len(llm.calls) == 50
    assert all(email.processed_at for email in emails(db))
    # Only the 20 left over were read from Gmail again.
    assert len(gmail.called("messages.get")) == 70

    third = sync_once(db, account)
    assert third.emails_classified == 0


def test_failed_classifications_count_against_the_cap(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_classifications_per_run", 2)
    inbox = [mail(f"m{number}", ACME, "Your application", None, number) for number in range(3)]
    use_gmail(FakeGmail(messages=inbox))
    llm = use_llm(monkeypatch, MALFORMED, MALFORMED, answer())

    run = sync_once(db, account)

    assert run.emails_classified == 1
    assert len(llm.calls) == 3
    assert [email.classification_attempts for email in emails(db)] == [1, 0, 0]
    assert [email.processed_at is not None for email in emails(db)] == [False, True, False]


# --- end to end: the three protections against writing something twice


def test_a_rejection_email_moves_a_card_and_queues_a_receipt(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    rejection = mail("r1", ACME, REJECTION, "t1")
    gmail = use_gmail(FakeGmail(messages=[rejection]))
    llm = use_llm(monkeypatch, answer(status="rejected", confidence=0.91))

    # 1. A rejection arrives.
    first = sync_once(db, account)

    assert (first.result, first.emails_classified) == (SyncResult.OK, 1)
    (application,) = applications(db)
    assert (application.company, application.role) == ("Acme Corp", "React Developer")
    assert application.status == Status.REJECTED
    assert application.needs_review is False
    (event,) = events(db)
    assert (event.from_status, event.to_status) == (None, Status.REJECTED)
    (job,) = jobs(db)
    assert (job.state, job.status_event_id) == (JobState.PENDING, event.id)
    texts = [line["text"] for line in job.payload["lines"]]
    assert {"Acme Corp", "REJECTED", "match 91%"} <= set(texts)

    # 2. Gmail reports the same message again: nothing is written twice.
    gmail.history_pages = [{"history": [added("r1")], "historyId": "150"}]
    second = sync_once(db, account)

    assert (second.result, second.emails_seen) == (SyncResult.OK, 1)
    assert (second.emails_new, second.emails_classified) == (0, 0)
    assert len(llm.calls) == 1
    assert (len(emails(db)), len(applications(db)), len(events(db)), len(jobs(db))) == (1, 1, 1, 1)

    # 3. A reply in the same thread moves the status of the same application.
    arrive(gmail, mail("r2", "Jane <jane@gmail.com>", "Re: one more thing", "t1", 120))
    use_llm(monkeypatch, answer(status="replied", company=None, role=None))
    third = sync_once(db, account)

    assert (third.emails_new, third.emails_classified) == (1, 1)
    db.expire_all()
    assert [saved.id for saved in applications(db)] == [application.id]
    assert application.status == Status.REPLIED
    assert [email.application_id for email in emails(db)] == [application.id] * 2
    assert [(saved.from_status, saved.to_status) for saved in events(db)] == [
        (None, Status.REJECTED),
        (Status.REJECTED, Status.REPLIED),
    ]
    assert len(jobs(db)) == 2
    assert len({saved.status_event_id for saved in jobs(db)}) == 2


def test_the_same_status_in_a_second_email_prints_no_second_receipt(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = use_gmail(FakeGmail(messages=[mail("r1", ACME, REJECTION, "t1")]))
    use_llm(monkeypatch, answer(status="rejected"))
    sync_once(db, account)

    arrive(gmail, mail("r2", ACME, REJECTION, "t1", 30))
    use_llm(monkeypatch, answer(status="rejected"))
    run = sync_once(db, account)

    assert run.emails_classified == 1
    assert (len(emails(db)), len(applications(db)), len(events(db)), len(jobs(db))) == (2, 1, 1, 1)
