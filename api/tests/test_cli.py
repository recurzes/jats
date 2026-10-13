import pytest
from gmail_fake import FakeGmail, message
from llm_fake import use_llm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.auth.device import verify_device_key
from app.config import get_settings
from app.gmail.models import Email, GmailAccount, SyncRun, SyncTrigger
from app.printing.models import Device, JobState, PrintJob


def test_create_device_stores_only_the_hash(
    db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.run(["create-device", "desk-esp32"], db)

    key = capsys.readouterr().out.strip().splitlines()[-1]
    device = db.scalars(select(Device)).one()
    assert device.name == "desk-esp32"
    assert device.user_id == get_settings().owner_user_id
    assert device.key_hash != key
    assert verify_device_key(key, device.key_hash)


def test_enqueue_test_inserts_a_pending_job(db: Session) -> None:
    cli.run(["enqueue-test", "--status", "REJECTED"], db)

    job = db.scalars(select(PrintJob)).one()
    assert job.state == JobState.PENDING
    assert job.payload["cut"] is True
    assert {"text": "REJECTED", "align": "center", "bold": True} in job.payload["lines"]
    assert "id" not in job.payload


def test_gmail_address_prints_the_connected_address(
    db: Session, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    account = GmailAccount(
        user_id=get_settings().owner_user_id, email_address="me@example.com", refresh_token_enc="x"
    )
    db.add(account)
    db.commit()
    monkeypatch.setattr(cli, "get_gmail_service", lambda found: found)
    monkeypatch.setattr(cli, "get_email_address", lambda service: service.email_address)

    cli.run(["gmail-address"], db)

    assert capsys.readouterr().out.strip() == "me@example.com"


def test_gmail_address_without_an_account(db: Session) -> None:
    with pytest.raises(SystemExit, match="No Gmail account"):
        cli.run(["gmail-address"], db)


def connect_gmail(db: Session, monkeypatch: pytest.MonkeyPatch, gmail: FakeGmail) -> None:
    db.add(
        GmailAccount(
            user_id=get_settings().owner_user_id,
            email_address="me@example.com",
            refresh_token_enc="x",
        )
    )
    db.commit()
    monkeypatch.setattr(cli, "get_gmail_service", lambda account: gmail)
    monkeypatch.setattr("app.gmail.sync.get_gmail_service", lambda account: gmail)


def test_gmail_count_prints_the_messages_of_the_last_7_days(
    db: Session, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = FakeGmail(messages=[message("a"), message("b"), message("c")])
    connect_gmail(db, monkeypatch, gmail)

    cli.run(["gmail-count"], db)

    assert capsys.readouterr().out.strip() == "3 messages in the last 7 days"
    assert gmail.called("messages.list")[0]["q"] == "newer_than:7d"


def test_sync_stores_emails_and_running_it_twice_adds_no_duplicates(
    db: Session, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    connect_gmail(db, monkeypatch, FakeGmail(messages=[message("a"), message("b")]))

    cli.run(["sync"], db)
    cli.run(["sync"], db)

    assert capsys.readouterr().out.splitlines() == [
        "Sync ok: 2 seen, 2 new, 0 classified",
        "Sync ok: 0 seen, 0 new, 0 classified",
    ]
    assert len(db.scalars(select(Email)).all()) == 2
    assert {run.trigger for run in db.scalars(select(SyncRun))} == {SyncTrigger.MANUAL}


@pytest.mark.parametrize("command", ["gmail-count", "sync"])
def test_gmail_commands_without_an_account(db: Session, command: str) -> None:
    with pytest.raises(SystemExit, match="No Gmail account"):
        cli.run([command], db)


def test_llm_ping_prints_the_reply(
    db: Session, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_llm(monkeypatch, '{"ok": true}')

    cli.run(["llm-ping"], db)

    assert capsys.readouterr().out.strip() == '{"ok": true}'
