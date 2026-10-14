import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from builders import add_account, add_email
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.gmail.models import AccountState, SyncResult, SyncRun, SyncTrigger
from app.printing.models import Device, JobState, PrintJob

Headers = dict[str, str]


def test_status_of_an_empty_system(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/status", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "last_sync": None,
        "gmail": {"state": "not_connected", "address": None},
        "device": {"last_seen_at": None, "online": False},
        "queue": {"pending": 0, "failed": 0},
        "failed_classifications": 0,
    }


def test_status_shows_the_gmail_account(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    account = add_account(db)

    assert client.get("/status", headers=auth_headers).json()["gmail"] == {
        "state": "ok",
        "address": "me@example.com",
    }

    account.state = AccountState.NEEDS_REAUTH
    db.commit()

    assert client.get("/status", headers=auth_headers).json()["gmail"]["state"] == "needs_reauth"


def test_status_shows_the_latest_sync(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    now = datetime.now(UTC)
    db.add(
        SyncRun(
            trigger=SyncTrigger.SCHEDULE,
            result=SyncResult.OK,
            started_at=now - timedelta(minutes=10),
            finished_at=now - timedelta(minutes=10),
        )
    )
    db.add(
        SyncRun(
            trigger=SyncTrigger.MANUAL,
            result=SyncResult.ERROR,
            error="Gmail is down",
            started_at=now - timedelta(minutes=5),
            finished_at=now - timedelta(minutes=5),
        )
    )
    # Skipped because another sync held the lock, so it is not the last sync.
    db.add(
        SyncRun(
            trigger=SyncTrigger.SCHEDULE,
            result=SyncResult.SKIPPED_LOCKED,
            started_at=now - timedelta(minutes=1),
            finished_at=now - timedelta(minutes=1),
        )
    )
    db.commit()

    last_sync = client.get("/status", headers=auth_headers).json()["last_sync"]

    assert last_sync["result"] == "error"
    assert last_sync["trigger"] == "manual"
    assert last_sync["error"] == "Gmail is down"
    assert datetime.fromisoformat(last_sync["started_at"]) == now - timedelta(minutes=5)


def test_a_sync_that_is_still_running_has_no_result(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    db.add(SyncRun(trigger=SyncTrigger.SCHEDULE, started_at=datetime.now(UTC)))
    db.commit()

    last_sync = client.get("/status", headers=auth_headers).json()["last_sync"]

    assert last_sync["result"] is None
    assert last_sync["finished_at"] is None


def test_a_device_seen_just_now_is_online(
    client: TestClient, db: Session, device: Device, auth_headers: Headers
) -> None:
    device.last_seen_at = datetime.now(UTC) - timedelta(seconds=90)
    db.commit()

    status = client.get("/status", headers=auth_headers).json()["device"]

    assert status["online"] is True
    assert datetime.fromisoformat(status["last_seen_at"]) == device.last_seen_at


def test_a_stale_device_is_offline(
    client: TestClient, db: Session, device: Device, auth_headers: Headers
) -> None:
    device.last_seen_at = datetime.now(UTC) - timedelta(minutes=3)
    db.commit()

    status = client.get("/status", headers=auth_headers).json()["device"]

    assert status["online"] is False
    assert datetime.fromisoformat(status["last_seen_at"]) == device.last_seen_at


def test_a_device_that_never_polled_is_offline(
    client: TestClient, device: Device, auth_headers: Headers
) -> None:
    assert client.get("/status", headers=auth_headers).json()["device"] == {
        "last_seen_at": None,
        "online": False,
    }


def test_the_most_recently_seen_device_counts(
    client: TestClient, db: Session, device: Device, auth_headers: Headers
) -> None:
    device.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
    db.add(
        Device(
            user_id=device.user_id, name="new", key_hash="x" * 64, last_seen_at=datetime.now(UTC)
        )
    )
    db.commit()

    assert client.get("/status", headers=auth_headers).json()["device"]["online"] is True


def test_status_counts_pending_and_failed_jobs(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    states = [JobState.PENDING, JobState.PENDING, JobState.FAILED, JobState.CLAIMED]
    db.add_all(PrintJob(payload={}, state=state) for state in [*states, JobState.PRINTED])
    db.commit()

    assert client.get("/status", headers=auth_headers).json()["queue"] == {
        "pending": 2,
        "failed": 1,
    }


def test_status_counts_the_emails_the_classifier_gave_up_on(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    account = add_account(db)
    now = datetime.now(UTC)
    add_email(db, account, "gave-up", classification={"error": "Invalid JSON"}, processed_at=now)
    add_email(db, account, "classified", classification={"is_job_related": False}, processed_at=now)
    # Failed once, but it will be tried again.
    add_email(db, account, "retrying", classification_attempts=1)

    assert client.get("/status", headers=auth_headers).json()["failed_classifications"] == 1


def test_status_needs_a_token(client: TestClient) -> None:
    response = client.get("/status")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_status_is_owner_only(client: TestClient, make_token: Callable[..., str]) -> None:
    headers = {"Authorization": f"Bearer {make_token(sub=uuid.uuid4())}"}

    response = client.get("/status", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_OWNER"
