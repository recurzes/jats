"""The sync loop: new Gmail messages become `emails` rows, one `sync_runs` row per run."""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.classifier.prefilter import is_candidate
from app.config import get_settings
from app.db import SessionLocal, engine
from app.gmail.client import (
    GmailAuthError,
    GmailHistoryExpiredError,
    get_current_history_id,
    get_gmail_service,
    list_message_ids,
    list_new_message_ids_since,
)
from app.gmail.models import AccountState, Email, GmailAccount, SyncResult, SyncRun, SyncTrigger
from app.gmail.parse import fetch_message

logger = logging.getLogger(__name__)

SYNC_LOCK_KEY = 0x6A617473  # "jats" in ASCII


@dataclass
class _Counts:
    seen: int = 0
    new: int = 0


@contextmanager
def sync_lock() -> Iterator[bool]:
    """Try to take the Postgres advisory lock that lets one sync run at a time.

    Yields whether it was taken. The lock lives on a connection of its own for as long as the
    block runs, so the database URL has to be a direct or session-pooled connection: a
    transaction pooler would hand that connection to someone else.
    """
    with engine.connect() as connection:
        locked = bool(connection.scalar(select(func.pg_try_advisory_lock(SYNC_LOCK_KEY))))
        # The lock belongs to the connection, so no transaction has to stay open for it.
        connection.commit()
        try:
            yield locked
        finally:
            if locked:
                connection.scalar(select(func.pg_advisory_unlock(SYNC_LOCK_KEY)))
                connection.commit()


def _list_ids(service: Any, account: GmailAccount) -> tuple[list[str], str, bool]:
    """The message ids to look at, oldest first, the history id to store once they are saved,
    and whether an expired history id forced the 7-day listing."""
    if account.history_id:
        try:
            ids, history_id = list_new_message_ids_since(service, account.history_id)
            return ids, history_id, False
        except GmailHistoryExpiredError:
            logger.warning("The Gmail history id expired; listing the last 7 days instead")

    # Read before listing, so mail that arrives mid-sync is caught by the next run.
    history_id = get_current_history_id(service)
    ids = list_message_ids(service)
    ids.reverse()
    return ids, history_id, account.history_id is not None


def _sync(db: Session, account: GmailAccount, counts: _Counts) -> SyncResult:
    account_id = account.id
    service = get_gmail_service(account)
    ids, history_id, fell_back = _list_ids(service, account)
    counts.seen = len(ids)

    stored = set(db.scalars(select(Email.gmail_message_id).where(Email.gmail_message_id.in_(ids))))
    for message_id in ids:
        if message_id in stored:
            continue
        parsed = fetch_message(service, message_id)
        if parsed is None:
            continue
        # parsed.body stays in memory: it is for the classifier and is never stored.
        db.add(
            Email(
                account_id=account_id,
                gmail_message_id=parsed.gmail_message_id,
                thread_id=parsed.thread_id,
                from_address=parsed.from_address,
                from_domain=parsed.from_domain,
                subject=parsed.subject,
                snippet=parsed.snippet,
                received_at=parsed.received_at,
                is_candidate=is_candidate(parsed.from_domain, parsed.subject),
            )
        )
        db.commit()
        counts.new += 1

    # Only after every row is committed: a crash before this re-reads mail instead of losing it.
    account.history_id = history_id
    db.commit()
    return SyncResult.FALLBACK_FULL if fell_back else SyncResult.OK


def run_sync(db: Session, account: GmailAccount, trigger: SyncTrigger) -> SyncRun:
    """Sync the account once and record the run. Failures are recorded, not raised."""
    # Timed by this process's clock at both ends, so the duration cannot come out negative.
    run = SyncRun(trigger=trigger, started_at=datetime.now(UTC))
    db.add(run)
    db.commit()

    counts = _Counts()
    result = SyncResult.ERROR
    error: str | None = None
    with sync_lock() as locked:
        try:
            result = _sync(db, account, counts) if locked else SyncResult.SKIPPED_LOCKED
        except GmailAuthError as exc:
            db.rollback()
            error = str(exc)
            # The scheduler leaves the account alone until Gmail is connected again.
            account.state = AccountState.NEEDS_REAUTH
            account.last_error = error
            logger.warning("Gmail sync stopped: the account has to be connected again")
        except Exception as exc:
            db.rollback()
            error = str(exc) or type(exc).__name__
            logger.exception("Gmail sync failed")
        finally:
            run.result = result
            run.emails_seen = counts.seen
            run.emails_new = counts.new
            run.error = error
            run.finished_at = datetime.now(UTC)
            db.commit()

    summary = {
        "sync_run_id": str(run.id),
        "trigger": run.trigger,
        "result": run.result,
        "emails_seen": run.emails_seen,
        "emails_new": run.emails_new,
        "emails_classified": run.emails_classified,
        "duration_ms": round((run.finished_at - run.started_at).total_seconds() * 1000),
    }
    logger.info("Gmail sync finished", extra={"data": summary})
    return run


def find_account(db: Session, user_id: uuid.UUID) -> GmailAccount | None:
    return db.scalar(select(GmailAccount).where(GmailAccount.user_id == user_id))


def sync_owner_account(trigger: SyncTrigger) -> None:
    """Run one sync in a session of its own: the scheduler job and the body of `POST /sync`.

    Does nothing while no account is connected or the account needs to be connected again.
    """
    with SessionLocal() as db:
        account = find_account(db, get_settings().owner_user_id)
        if account is None or account.state != AccountState.OK:
            logger.debug("Gmail sync skipped: no account is connected, or it needs reconnecting")
            return
        run_sync(db, account, trigger)
