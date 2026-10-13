"""Owner commands, run from api/: python -m app.cli <command>."""

import argparse
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.auth.device import register_device
from app.classifier.llm import chat_json
from app.config import get_settings
from app.db import SessionLocal
from app.gmail.client import get_email_address, get_gmail_service, list_message_ids
from app.gmail.models import GmailAccount, SyncTrigger
from app.gmail.sync import find_account, run_sync
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


def _gmail_account(db: Session) -> GmailAccount:
    account = find_account(db, get_settings().owner_user_id)
    if account is None:
        raise SystemExit("No Gmail account is connected yet")
    return account


def gmail_address(db: Session) -> None:
    print(get_email_address(get_gmail_service(_gmail_account(db))))


def gmail_count(db: Session) -> None:
    ids = list_message_ids(get_gmail_service(_gmail_account(db)))
    print(f"{len(ids)} messages in the last 7 days")


def sync(db: Session) -> None:
    run = run_sync(db, _gmail_account(db), SyncTrigger.MANUAL)
    print(
        f"Sync {run.result}: {run.emails_seen} seen, {run.emails_new} new, "
        f"{run.emails_classified} classified"
    )
    if run.error:
        print(run.error)


def llm_ping() -> None:
    print(chat_json("Answer with JSON only.", 'Return the JSON object {"ok": true}.'))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    device = commands.add_parser("create-device", help="Create a device and print its key once")
    device.add_argument("name", help="For example: desk-esp32")

    test_job = commands.add_parser("enqueue-test", help="Queue a sample receipt")
    test_job.add_argument("--status", default="REJECTED")

    commands.add_parser("gmail-address", help="Ask Gmail for the connected address")
    commands.add_parser("gmail-count", help="Count the messages of the last 7 days")
    commands.add_parser("sync", help="Run one Gmail sync now")
    commands.add_parser("llm-ping", help="Ask the AI provider for a one-line reply")

    return parser


def run(argv: Sequence[str] | None, db: Session) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "create-device":
        create_device(db, args.name)
    elif args.command == "enqueue-test":
        enqueue_test(db, args.status)
    elif args.command == "gmail-address":
        gmail_address(db)
    elif args.command == "gmail-count":
        gmail_count(db)
    elif args.command == "llm-ping":
        llm_ping()
    else:
        sync(db)


def main() -> None:
    with SessionLocal() as db:
        run(None, db)


if __name__ == "__main__":
    main()
