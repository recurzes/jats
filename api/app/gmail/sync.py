"""The sync loop: new Gmail messages become `emails` rows, and the candidates among them are
classified and applied to their applications. One `sync_runs` row per run."""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.applications.matcher import find_by_thread
from app.applications.service import apply_classification
from app.classifier.llm import LLMError
from app.classifier.prefilter import is_candidate
from app.classifier.service import ClassificationFailed, classify_and_store
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
from app.gmail.parse import ParsedEmail, fetch_message

logger = logging.getLogger(__name__)

SYNC_LOCK_KEY = 0x6A617473  # "jats" in ASCII

# An email the AI cannot classify is tried on this many syncs, then given up on.
MAX_CLASSIFICATION_ATTEMPTS = 3


@dataclass
class _Counts:
    seen: int = 0
    new: int = 0
    classified: int = 0


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

    budget = get_settings().max_classifications_per_run
    # Bodies are never stored, so the ones just fetched are kept here for the classifier.
    fetched: dict[str, ParsedEmail] = {}
    stored = set(db.scalars(select(Email.gmail_message_id).where(Email.gmail_message_id.in_(ids))))
    for message_id in ids:
        if message_id in stored:
            continue
        parsed = fetch_message(service, message_id)
        if parsed is None:
            continue
        candidate = is_candidate(
            parsed.from_domain,
            parsed.subject,
            in_known_thread=find_by_thread(db, parsed.thread_id) is not None,
        )
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
                is_candidate=candidate,
            )
        )
        db.commit()
        counts.new += 1
        if candidate and len(fetched) < budget:
            fetched[parsed.gmail_message_id] = parsed

    # Only after every row is committed: a crash before this re-reads mail instead of losing it.
    account.history_id = history_id
    db.commit()

    _classify_candidates(db, service, account_id, fetched, budget, counts)
    return SyncResult.FALLBACK_FULL if fell_back else SyncResult.OK


def _next_candidate(db: Session, account_id: uuid.UUID, tried: list[uuid.UUID]) -> Email | None:
    """The oldest candidate still waiting for the AI: new, left over by the cap, or a retry."""
    return db.scalar(
        select(Email)
        .where(
            Email.account_id == account_id,
            Email.is_candidate,
            Email.processed_at.is_(None),
            Email.classification_attempts < MAX_CLASSIFICATION_ATTEMPTS,
            Email.id.not_in(tried),
        )
        .order_by(Email.received_at, Email.gmail_message_id)
        .limit(1)
    )


def _give_up(db: Session, email: Email, reason: str) -> None:
    """Mark the email processed without a classification, so it is never tried again."""
    email.classification = {"error": reason}
    email.processed_at = datetime.now(UTC)
    db.commit()
    logger.warning(
        "Gave up classifying an email",
        extra={
            "data": {
                "gmail_message_id": email.gmail_message_id,
                "attempts": email.classification_attempts,
                "reason": reason,
            }
        },
    )


def _classify_and_apply(db: Session, email: Email, parsed: ParsedEmail) -> str | None:
    """Classify one email and apply the result, in one transaction.

    Returns why it failed, or None when the email is done. A failure counts one attempt.
    """
    message_id = email.gmail_message_id
    try:
        result = classify_and_store(db, email, parsed)
        if isinstance(result, ClassificationFailed):
            db.commit()
            return result.reason
        if result is not None and apply_classification(db, email, result) is not None:
            # The thread has an application now, so its mail the prefilter turned down counts.
            db.execute(
                update(Email)
                .where(
                    Email.thread_id == email.thread_id,
                    Email.is_candidate.is_(False),
                    Email.processed_at.is_(None),
                )
                .values(is_candidate=True)
            )
        db.commit()
        return None
    except LLMError:
        # The provider is down or refuses the key. That is not this email's fault.
        raise
    except Exception as exc:
        # One bad email must never block the others.
        db.rollback()
        logger.exception(
            "Could not process a classified email", extra={"data": {"gmail_message_id": message_id}}
        )
        email.classification_attempts += 1
        db.commit()
        return f"Could not apply the classification ({type(exc).__name__})"


def _classify_candidates(
    db: Session,
    service: Any,
    account_id: uuid.UUID,
    fetched: dict[str, ParsedEmail],
    budget: int,
    counts: _Counts,
) -> None:
    """Send waiting candidates to the AI, oldest first, until the run's budget is spent."""
    tried: list[uuid.UUID] = []
    while budget > 0 and (email := _next_candidate(db, account_id, tried)) is not None:
        tried.append(email.id)
        parsed = fetched.pop(email.gmail_message_id, None) or fetch_message(
            service, email.gmail_message_id
        )
        if parsed is None:
            _give_up(db, email, "The message no longer exists in Gmail")
            continue

        budget -= 1
        reason = _classify_and_apply(db, email, parsed)
        if reason is None:
            counts.classified += 1
        elif email.classification_attempts >= MAX_CLASSIFICATION_ATTEMPTS:
            _give_up(db, email, reason)


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
            run.emails_classified = counts.classified
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
