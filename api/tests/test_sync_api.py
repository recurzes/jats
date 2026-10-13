import uuid
from collections.abc import Callable
from contextlib import nullcontext
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from gmail_fake import FakeGmail, message
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import main
from app.config import get_settings
from app.gmail import scheduler, sync
from app.gmail.models import AccountState, Email, GmailAccount, SyncResult, SyncRun, SyncTrigger
from app.main import app

Headers = dict[str, str]


@pytest.fixture
def account(db: Session) -> GmailAccount:
    account = GmailAccount(
        user_id=get_settings().owner_user_id,
        email_address="me@example.com",
        refresh_token_enc="enc",
    )
    db.add(account)
    db.commit()
    return account


@pytest.fixture
def gmail(db: Session, monkeypatch: pytest.MonkeyPatch) -> FakeGmail:
    """A fake inbox, and the test's session for the sync that runs after the response."""
    gmail = FakeGmail(messages=[message("a")])
    monkeypatch.setattr(sync, "get_gmail_service", lambda account: gmail)
    monkeypatch.setattr(sync, "SessionLocal", lambda: nullcontext(db))
    return gmail


# --- POST /sync


def test_post_sync_runs_a_manual_sync(
    client: TestClient, db: Session, account: GmailAccount, gmail: FakeGmail, auth_headers: Headers
) -> None:
    response = client.post("/sync", headers=auth_headers)

    assert response.status_code == 202
    assert response.json() == {"status": "started"}
    run = db.scalars(select(SyncRun)).one()
    assert run.trigger == SyncTrigger.MANUAL
    assert run.result == SyncResult.OK
    assert run.emails_new == 1
    assert db.scalars(select(Email.gmail_message_id)).all() == ["a"]


def test_post_sync_needs_a_token(client: TestClient, db: Session, gmail: FakeGmail) -> None:
    response = client.post("/sync")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"
    assert db.scalars(select(SyncRun)).all() == []


def test_post_sync_is_owner_only(
    client: TestClient, db: Session, gmail: FakeGmail, make_token: Callable[..., str]
) -> None:
    headers = {"Authorization": f"Bearer {make_token(sub=uuid.uuid4())}"}

    response = client.post("/sync", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_OWNER"
    assert db.scalars(select(SyncRun)).all() == []


def test_post_sync_without_a_gmail_account(
    client: TestClient, db: Session, gmail: FakeGmail, auth_headers: Headers
) -> None:
    response = client.post("/sync", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GMAIL_NOT_CONNECTED"
    assert db.scalars(select(SyncRun)).all() == []


def test_post_sync_when_gmail_needs_reconnecting(
    client: TestClient, db: Session, account: GmailAccount, gmail: FakeGmail, auth_headers: Headers
) -> None:
    account.state = AccountState.NEEDS_REAUTH
    db.commit()

    response = client.post("/sync", headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GMAIL_NEEDS_REAUTH"
    assert db.scalars(select(SyncRun)).all() == []
    assert gmail.calls == []


# --- the scheduler


def test_the_scheduler_runs_the_sync_job_on_the_configured_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "sync_interval_minutes", 7)

    started = scheduler.start_scheduler()
    try:
        assert started.running
        job = started.get_job(scheduler.SYNC_JOB_ID)
        assert job.func is sync.sync_owner_account
        assert job.args == (SyncTrigger.SCHEDULE,)
        assert job.trigger.interval == timedelta(minutes=7)
        assert job.max_instances == 1
        assert job.coalesce is True
    finally:
        started.shutdown(wait=False)
    assert not started.running


class RecordingScheduler:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> "RecordingScheduler":
        self.events.append("start")
        return self

    def shutdown(self) -> None:
        self.events.append("shutdown")


def test_the_app_starts_and_stops_the_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = RecordingScheduler()
    monkeypatch.setattr(get_settings(), "scheduler_enabled", True)
    monkeypatch.setattr(main, "start_scheduler", recorder.start)

    with TestClient(app):
        assert recorder.events == ["start"]

    assert recorder.events == ["start", "shutdown"]


def test_scheduler_enabled_false_turns_the_scheduler_off(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = RecordingScheduler()
    monkeypatch.setattr(main, "start_scheduler", recorder.start)

    # conftest sets SCHEDULER_ENABLED=false for the whole suite.
    assert get_settings().scheduler_enabled is False
    with TestClient(app):
        pass

    assert recorder.events == []
