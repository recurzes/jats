import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.auth.device import verify_device_key
from app.config import get_settings
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
