"""Owner commands, run from api/: python -m app.cli <command>."""

import argparse
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.auth.device import generate_device_key, hash_device_key
from app.config import get_settings
from app.db import SessionLocal
from app.printing import queue
from app.printing.models import Device
from app.printing.receipt import render_status_receipt


def create_device(db: Session, name: str) -> None:
    key = generate_device_key()
    device = Device(user_id=get_settings().owner_user_id, name=name, key_hash=hash_device_key(key))
    db.add(device)
    db.commit()
    print(f"Created device {name!r} ({device.id})")
    print("Device key, shown only this once:")
    print(key)


def enqueue_test(db: Session, status: str) -> None:
    receipt = render_status_receipt(
        company="Acme Corp",
        role="React Developer",
        status=status,
        when=datetime.now(),
        subject="Update on your application",
        confidence=0.93,
    )
    job = queue.enqueue(db, receipt)
    db.commit()
    print(f"Queued print job {job.id} ({job.state})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    device = commands.add_parser("create-device", help="Create a device and print its key once")
    device.add_argument("name", help="For example: desk-esp32")

    test_job = commands.add_parser("enqueue-test", help="Queue a sample receipt")
    test_job.add_argument("--status", default="REJECTED")

    return parser


def run(argv: Sequence[str] | None, db: Session) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "create-device":
        create_device(db, args.name)
    else:
        enqueue_test(db, args.status)


def main() -> None:
    with SessionLocal() as db:
        run(None, db)


if __name__ == "__main__":
    main()
