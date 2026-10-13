import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.applications.models import Application, EventSource, StatusEvent
from app.classifier.schema import Status
from app.gmail.models import AccountState, Email, GmailAccount, SyncResult, SyncRun, SyncTrigger
from app.printing.models import Device, JobState, PrintJob


def test_insert_device(db: Session) -> None:
    device = Device(user_id=uuid.uuid4(), name="desk-esp32", key_hash="a" * 64)
    db.add(device)
    db.commit()

    saved = db.get(Device, device.id)
    assert saved.name == "desk-esp32"
    assert saved.created_at is not None
    assert saved.last_seen_at is None


def test_device_key_hash_is_unique(db: Session) -> None:
    db.add(Device(user_id=uuid.uuid4(), name="one", key_hash="b" * 64))
    db.add(Device(user_id=uuid.uuid4(), name="two", key_hash="b" * 64))

    with pytest.raises(IntegrityError):
        db.commit()


def test_insert_print_job_uses_defaults(db: Session) -> None:
    job = PrintJob(payload={"lines": [], "cut": True})
    db.add(job)
    db.commit()

    saved = db.get(PrintJob, job.id)
    assert saved.state == JobState.PENDING
    assert saved.attempts == 0
    assert saved.payload == {"lines": [], "cut": True}
    assert saved.device_id is None
    assert saved.status_event_id is None
    assert saved.created_at is not None


def test_print_job_rejects_an_unknown_state(db: Session) -> None:
    db.add(PrintJob(payload={}, state="lost"))

    with pytest.raises(IntegrityError):
        db.commit()


def gmail_account(user_id: uuid.UUID, **fields: object) -> GmailAccount:
    return GmailAccount(
        user_id=user_id, email_address="me@example.com", refresh_token_enc="enc", **fields
    )


def test_insert_gmail_account_uses_defaults(db: Session) -> None:
    account = gmail_account(uuid.uuid4())
    db.add(account)
    db.commit()

    saved = db.get(GmailAccount, account.id)
    assert saved.state == AccountState.OK
    assert saved.history_id is None
    assert saved.last_error is None
    assert saved.connected_at is not None


def test_one_gmail_account_per_user(db: Session) -> None:
    user_id = uuid.uuid4()
    db.add(gmail_account(user_id))
    db.add(gmail_account(user_id))

    with pytest.raises(IntegrityError):
        db.commit()


def test_gmail_account_rejects_an_unknown_state(db: Session) -> None:
    db.add(gmail_account(uuid.uuid4(), state="broken"))

    with pytest.raises(IntegrityError):
        db.commit()


def email(account: GmailAccount, **fields: object) -> Email:
    values = {
        "account_id": account.id,
        "gmail_message_id": "18f0a1b2c3d4e5f6",
        "thread_id": "18f0a1b2c3d4e5f6",
        "from_address": "careers@acme.example",
        "from_domain": "acme.example",
        "subject": "We received your application",
        "snippet": "Thank you for applying",
        "received_at": datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
    }
    return Email(**(values | fields))


@pytest.fixture
def account(db: Session) -> GmailAccount:
    account = gmail_account(uuid.uuid4())
    db.add(account)
    db.commit()
    return account


def test_insert_email_uses_defaults(db: Session, account: GmailAccount) -> None:
    row = email(account)
    db.add(row)
    db.commit()

    saved = db.get(Email, row.id)
    assert saved.is_candidate is False
    assert saved.classification is None
    assert saved.confidence is None
    assert saved.classification_attempts == 0
    assert saved.processed_at is None
    assert saved.created_at is not None


def test_email_stores_a_classification(db: Session, account: GmailAccount) -> None:
    row = email(account, is_candidate=True, classification={"status": "REJECTED"}, confidence=0.93)
    db.add(row)
    db.commit()

    saved = db.get(Email, row.id)
    assert saved.classification == {"status": "REJECTED"}
    assert saved.confidence == pytest.approx(0.93)


def test_gmail_message_id_is_unique(db: Session, account: GmailAccount) -> None:
    db.add(email(account))
    db.add(email(account, thread_id="another-thread"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_email_needs_an_existing_account(db: Session) -> None:
    db.add(email(gmail_account(uuid.uuid4(), id=uuid.uuid4())))

    with pytest.raises(IntegrityError):
        db.commit()


def test_insert_sync_run_uses_defaults(db: Session) -> None:
    run = SyncRun(trigger=SyncTrigger.SCHEDULE)
    db.add(run)
    db.commit()

    saved = db.get(SyncRun, run.id)
    assert saved.started_at is not None
    assert saved.finished_at is None
    assert saved.result is None
    assert (saved.emails_seen, saved.emails_new, saved.emails_classified) == (0, 0, 0)
    assert saved.error is None


@pytest.mark.parametrize("result", list(SyncResult))
def test_sync_run_accepts_every_result(db: Session, result: SyncResult) -> None:
    run = SyncRun(trigger=SyncTrigger.MANUAL, result=result)
    db.add(run)
    db.commit()

    assert db.get(SyncRun, run.id).result == result


@pytest.mark.parametrize("fields", [{"trigger": "cron"}, {"trigger": "manual", "result": "fine"}])
def test_sync_run_rejects_unknown_values(db: Session, fields: dict[str, str]) -> None:
    db.add(SyncRun(**fields))

    with pytest.raises(IntegrityError):
        db.commit()


def new_application(**fields: object) -> Application:
    values = {"user_id": uuid.uuid4(), "company": "Acme Corp", "company_key": "acme"}
    return Application(**(values | {"status": Status.ACKNOWLEDGED} | fields))


@pytest.fixture
def application(db: Session) -> Application:
    application = new_application()
    db.add(application)
    db.commit()
    return application


def test_insert_application_uses_defaults(db: Session, application: Application) -> None:
    saved = db.get(Application, application.id)
    assert saved.needs_review is False
    assert saved.role is None
    assert saved.thread_id is None
    assert saved.first_seen_at is not None
    assert saved.last_event_at is not None


@pytest.mark.parametrize("status", list(Status))
def test_application_accepts_every_status(db: Session, status: Status) -> None:
    application = new_application(status=status)
    db.add(application)
    db.commit()

    assert db.get(Application, application.id).status == status


def test_application_rejects_an_unknown_status(db: Session) -> None:
    db.add(new_application(status="hired"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_email_links_to_an_application(
    db: Session, account: GmailAccount, application: Application
) -> None:
    row = email(account, application_id=application.id)
    db.add(row)
    db.commit()

    assert db.get(Email, row.id).application_id == application.id


def test_email_needs_an_existing_application(db: Session, account: GmailAccount) -> None:
    db.add(email(account, application_id=uuid.uuid4()))

    with pytest.raises(IntegrityError):
        db.commit()


def event(application: Application, **fields: object) -> StatusEvent:
    values = {"application_id": application.id, "to_status": Status.REJECTED}
    return StatusEvent(**(values | {"source": EventSource.AI} | fields))


def test_insert_status_event(db: Session, account: GmailAccount, application: Application) -> None:
    row = email(account)
    db.add(row)
    db.flush()
    saved = event(application, email_id=row.id, from_status=Status.ACKNOWLEDGED)
    db.add(saved)
    db.commit()

    saved = db.get(StatusEvent, saved.id)
    assert (saved.from_status, saved.to_status) == (Status.ACKNOWLEDGED, Status.REJECTED)
    assert saved.source == EventSource.AI
    assert saved.created_at is not None


def test_one_email_causes_at_most_one_event(
    db: Session, account: GmailAccount, application: Application
) -> None:
    row = email(account)
    db.add(row)
    db.flush()
    db.add(event(application, email_id=row.id))
    db.add(event(application, email_id=row.id, to_status=Status.REPLIED))

    with pytest.raises(IntegrityError):
        db.commit()


def test_manual_events_need_no_email(db: Session, application: Application) -> None:
    db.add(event(application, source=EventSource.MANUAL))
    db.add(event(application, source=EventSource.MANUAL, to_status=Status.REPLIED))
    db.commit()

    assert db.query(StatusEvent).filter_by(email_id=None).count() == 2


def test_status_event_rejects_an_unknown_source(db: Session, application: Application) -> None:
    db.add(event(application, source="robot"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_one_status_event_creates_at_most_one_print_job(
    db: Session, application: Application
) -> None:
    saved = event(application)
    db.add(saved)
    db.flush()
    db.add(PrintJob(payload={}, status_event_id=saved.id))
    db.add(PrintJob(payload={}, status_event_id=saved.id))

    with pytest.raises(IntegrityError):
        db.commit()


def test_print_jobs_without_an_event_are_not_limited(db: Session) -> None:
    db.add(PrintJob(payload={}))
    db.add(PrintJob(payload={}))
    db.commit()

    assert db.query(PrintJob).filter_by(status_event_id=None).count() == 2


def test_print_job_needs_an_existing_status_event(db: Session) -> None:
    db.add(PrintJob(payload={}, status_event_id=uuid.uuid4()))

    with pytest.raises(IntegrityError):
        db.commit()
