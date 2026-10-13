import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.printing import queue
from app.printing.models import Device, JobState, PrintJob
from app.printing.receipt import Receipt, ReceiptLine

NEXT_URL = "/device/jobs/next"
Headers = dict[str, str]


def enqueue(db: Session, text: str = "hello") -> PrintJob:
    job = queue.enqueue(db, Receipt(lines=[ReceiptLine(text=text)]))
    db.commit()
    return job


def expire_lease(db: Session, job: PrintJob) -> None:
    db.refresh(job)
    job.claimed_at = datetime.now(UTC) - timedelta(seconds=get_settings().lease_seconds + 1)
    db.commit()


def test_claim_returns_the_job_once_then_204(
    client: TestClient, db: Session, device: Device, device_headers: Headers
) -> None:
    job = enqueue(db)

    response = client.get(NEXT_URL, headers=device_headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(job.id),
        "lines": [{"text": "hello", "align": "left", "bold": False}],
        "cut": True,
    }
    db.refresh(job)
    assert job.state == JobState.CLAIMED
    assert job.claimed_at is not None
    assert job.device_id == device.id
    assert job.attempts == 1

    assert client.get(NEXT_URL, headers=device_headers).status_code == 204


def test_claim_takes_the_oldest_job_first(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    newer = enqueue(db, "newer")
    older = enqueue(db, "older")
    older.created_at = newer.created_at - timedelta(minutes=5)
    db.commit()

    response = client.get(NEXT_URL, headers=device_headers)

    assert response.json()["id"] == str(older.id)


def test_abandoned_job_returns_after_the_lease(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    assert client.get(NEXT_URL, headers=device_headers).status_code == 200
    assert client.get(NEXT_URL, headers=device_headers).status_code == 204

    expire_lease(db, job)
    response = client.get(NEXT_URL, headers=device_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(job.id)
    db.refresh(job)
    assert job.attempts == 2


def test_job_abandoned_at_the_attempt_limit_becomes_failed(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    for _ in range(get_settings().max_attempts):
        assert client.get(NEXT_URL, headers=device_headers).status_code == 200
        expire_lease(db, job)

    assert client.get(NEXT_URL, headers=device_headers).status_code == 204

    db.refresh(job)
    assert job.state == JobState.FAILED
    assert job.attempts == get_settings().max_attempts
    assert job.failure_reason == "lease_expired"


def test_ack_marks_the_job_printed(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    client.get(NEXT_URL, headers=device_headers)

    response = client.post(f"/device/jobs/{job.id}/ack", headers=device_headers)

    assert response.status_code == 200
    assert response.json() == {"id": str(job.id), "state": "printed"}
    db.refresh(job)
    assert job.state == JobState.PRINTED
    assert job.printed_at is not None


def test_repeat_ack_is_safe(client: TestClient, db: Session, device_headers: Headers) -> None:
    job = enqueue(db)
    client.get(NEXT_URL, headers=device_headers)
    client.post(f"/device/jobs/{job.id}/ack", headers=device_headers)
    db.refresh(job)
    first_printed_at = job.printed_at

    response = client.post(f"/device/jobs/{job.id}/ack", headers=device_headers)

    assert response.status_code == 200
    db.refresh(job)
    assert job.state == JobState.PRINTED
    assert job.printed_at == first_printed_at


def test_ack_unknown_id_returns_404(client: TestClient, device_headers: Headers) -> None:
    response = client.post(f"/device/jobs/{uuid.uuid4()}/ack", headers=device_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_ack_and_fail_need_a_device_key(client: TestClient, db: Session) -> None:
    job = enqueue(db)

    ack = client.post(f"/device/jobs/{job.id}/ack")
    fail = client.post(f"/device/jobs/{job.id}/fail", json={"reason": "other"})

    assert ack.status_code == fail.status_code == 401
    assert ack.json()["error"]["code"] == fail.json()["error"]["code"] == "DEVICE_AUTH"


def test_fail_stores_the_reason_and_requeues(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    client.get(NEXT_URL, headers=device_headers)

    response = client.post(
        f"/device/jobs/{job.id}/fail", headers=device_headers, json={"reason": "out_of_paper"}
    )

    assert response.status_code == 200
    assert response.json() == {"id": str(job.id), "state": "pending"}
    db.refresh(job)
    assert job.failure_reason == "out_of_paper"
    # No lease to wait for: the job is claimable again straight away.
    assert client.get(NEXT_URL, headers=device_headers).json()["id"] == str(job.id)


def test_fifth_failure_ends_the_job(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    states = []
    for _ in range(get_settings().max_attempts):
        assert client.get(NEXT_URL, headers=device_headers).status_code == 200
        response = client.post(
            f"/device/jobs/{job.id}/fail", headers=device_headers, json={"reason": "bt_connect"}
        )
        states.append(response.json()["state"])

    assert states == ["pending"] * 4 + ["failed"]
    assert client.get(NEXT_URL, headers=device_headers).status_code == 204
    db.refresh(job)
    assert job.state == JobState.FAILED
    assert job.failure_reason == "bt_connect"


def test_fail_rejects_an_unknown_reason(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    client.get(NEXT_URL, headers=device_headers)

    response = client.post(
        f"/device/jobs/{job.id}/fail", headers=device_headers, json={"reason": "gremlins"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


def test_fail_unknown_id_returns_404(client: TestClient, device_headers: Headers) -> None:
    response = client.post(
        f"/device/jobs/{uuid.uuid4()}/fail", headers=device_headers, json={"reason": "other"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_fail_does_not_undo_a_printed_job(
    client: TestClient, db: Session, device_headers: Headers
) -> None:
    job = enqueue(db)
    client.get(NEXT_URL, headers=device_headers)
    client.post(f"/device/jobs/{job.id}/ack", headers=device_headers)

    response = client.post(
        f"/device/jobs/{job.id}/fail", headers=device_headers, json={"reason": "other"}
    )

    assert response.json()["state"] == "printed"
