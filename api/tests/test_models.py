import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.gmail.models import AccountState, GmailAccount
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
