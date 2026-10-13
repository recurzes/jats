from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import cli
from app.auth.device import hash_device_key
from app.config import get_settings
from app.db import SessionLocal
from app.printing import queue
from app.printing.models import Device, JobState, PrintJob
from app.printing.receipt import Receipt, ReceiptLine

NEXT_URL = "/device/jobs/next"


def test_enqueue_claim_fail_claim_ack_then_empty(
    client: TestClient, db: Session, device_headers: dict[str, str]
) -> None:
    cli.run(["enqueue-test", "--status", "REJECTED"], db)

    first = client.get(NEXT_URL, headers=device_headers)
    assert first.status_code == 200
    job_id = first.json()["id"]
    assert first.json()["cut"] is True
    assert {"text": "REJECTED", "align": "center", "bold": True} in first.json()["lines"]

    failed = client.post(
        f"/device/jobs/{job_id}/fail", headers=device_headers, json={"reason": "bt_connect"}
    )
    assert failed.json() == {"id": job_id, "state": "pending"}

    second = client.get(NEXT_URL, headers=device_headers)
    assert second.status_code == 200
    assert second.json() == first.json()

    acked = client.post(f"/device/jobs/{job_id}/ack", headers=device_headers)
    assert acked.json() == {"id": job_id, "state": "printed"}

    assert client.get(NEXT_URL, headers=device_headers).status_code == 204

    job = db.get(PrintJob, job_id)
    assert job.state == JobState.PRINTED
    assert job.attempts == 2
    assert job.failure_reason == "bt_connect"


@pytest.fixture
def committed_job() -> Iterator[tuple[Device, PrintJob]]:
    """A device and a pending job that other connections can see, removed afterwards."""
    with SessionLocal() as setup:
        device = Device(
            user_id=get_settings().owner_user_id, name="flow", key_hash=hash_device_key("flow")
        )
        setup.add(device)
        job = queue.enqueue(setup, Receipt(lines=[ReceiptLine(text="only once")]))
        setup.commit()
        device_id, job_id = device.id, job.id
        setup.expunge_all()
    try:
        yield device, job
    finally:
        with SessionLocal() as cleanup:
            cleanup.execute(delete(PrintJob).where(PrintJob.id == job_id))
            cleanup.execute(delete(Device).where(Device.id == device_id))
            cleanup.commit()


def test_two_sessions_cannot_claim_the_same_job(committed_job: tuple[Device, PrintJob]) -> None:
    device, job = committed_job

    with SessionLocal() as first, SessionLocal() as second:
        # The first claim is flushed but not committed, so it still holds the row lock.
        claimed = queue.claim_next(first, device)
        assert claimed is not None and claimed.id == job.id

        # SKIP LOCKED: the second session gets nothing instead of waiting for the lock.
        assert queue.claim_next(second, device) is None
        second.rollback()

        first.commit()
        assert queue.claim_next(second, device) is None
