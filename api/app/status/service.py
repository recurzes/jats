"""The health of the pipeline, read from the other modules. Nothing here writes."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.gmail.models import Email, GmailAccount, SyncResult, SyncRun
from app.printing.models import Device, JobState, PrintJob
from app.status.schemas import (
    DeviceStatus,
    GmailState,
    GmailStatus,
    LastSync,
    QueueStatus,
    SystemStatus,
)

# A device that has not polled for this long is shown as offline.
ONLINE_WITHIN = timedelta(minutes=2)


def _last_sync(db: Session) -> LastSync | None:
    run = db.scalar(
        select(SyncRun)
        # A run that was skipped because another was already running says nothing new.
        .where(or_(SyncRun.result.is_(None), SyncRun.result != SyncResult.SKIPPED_LOCKED))
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    return LastSync.model_validate(run) if run else None


def _gmail(db: Session, user_id: uuid.UUID) -> GmailStatus:
    account = db.scalar(select(GmailAccount).where(GmailAccount.user_id == user_id))
    if account is None:
        return GmailStatus(state=GmailState.NOT_CONNECTED, address=None)
    return GmailStatus(state=GmailState(account.state), address=account.email_address)


def _device(db: Session, user_id: uuid.UUID) -> DeviceStatus:
    """The user's most recently seen device."""
    last_seen_at = db.scalar(select(func.max(Device.last_seen_at)).where(Device.user_id == user_id))
    online = last_seen_at is not None and datetime.now(UTC) - last_seen_at <= ONLINE_WITHIN
    return DeviceStatus(last_seen_at=last_seen_at, online=online)


def _queue(db: Session) -> QueueStatus:
    counts = dict(
        db.execute(
            select(PrintJob.state, func.count())
            .where(PrintJob.state.in_([JobState.PENDING, JobState.FAILED]))
            .group_by(PrintJob.state)
        ).all()
    )
    return QueueStatus(
        pending=counts.get(JobState.PENDING, 0), failed=counts.get(JobState.FAILED, 0)
    )


def _failed_classifications(db: Session, user_id: uuid.UUID) -> int:
    # Giving up on an email stores {"error": reason} in place of a classification.
    return db.scalar(
        select(func.count())
        .select_from(Email)
        .join(GmailAccount, GmailAccount.id == Email.account_id)
        .where(GmailAccount.user_id == user_id, Email.classification.has_key("error"))
    )


def read_status(db: Session, user_id: uuid.UUID) -> SystemStatus:
    return SystemStatus(
        last_sync=_last_sync(db),
        gmail=_gmail(db, user_id),
        device=_device(db, user_id),
        queue=_queue(db),
        failed_classifications=_failed_classifications(db, user_id),
    )
