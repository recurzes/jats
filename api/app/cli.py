"""Owner commands, run from api/: python -m app.cli <command>."""

import argparse
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.device import register_device
from app.config import get_settings
from app.db import SessionLocal
from app.gmail.client import get_email_address, get_gmail_service
from app.gmail.models import GmailAccount
from app.printing import queue
from app.printing.receipt import render_status_receipt


def create_device(db: Session, name: str) -> None:
    device, key = register_device(db, get_settings().owner_user_id, name)
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


def gmail_address(db: Session) -> None:
    account = db.scalar(
        select(GmailAccount).where(GmailAccount.user_id == get_settings().owner_user_id)
    )
    if account is None:
        raise SystemExit("No Gmail account is connected yet")
    print(get_email_address(get_gmail_service(account)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    device = commands.add_parser("create-device", help="Create a device and print its key once")
    device.add_argument("name", help="For example: desk-esp32")

    test_job = commands.add_parser("enqueue-test", help="Queue a sample receipt")
    test_job.add_argument("--status", default="REJECTED")

    commands.add_parser("gmail-address", help="Ask Gmail for the connected address")

    return parser


def run(argv: Sequence[str] | None, db: Session) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "create-device":
        create_device(db, args.name)
    elif args.command == "enqueue-test":
        enqueue_test(db, args.status)
    else:
        gmail_address(db)


def main() -> None:
    with SessionLocal() as db:
        run(None, db)


if __name__ == "__main__":
    main()
