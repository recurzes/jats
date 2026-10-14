import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.printing.models import Device, JobState, PrintJob
from app.printing.receipt import Receipt

# These functions flush but never commit, so a caller can queue a job in the same
# transaction as the change that caused it.


def enqueue(
    db: Session,
    receipt: Receipt,
    status_event_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
) -> PrintJob:
    job = PrintJob(
        payload=receipt.model_dump(mode="json", exclude={"id"}),
        status_event_id=status_event_id,
        application_id=application_id,
    )
    db.add(job)
    db.flush()
    return job


def enqueue_reprint(db: Session, receipt: Receipt, application_id: uuid.UUID) -> PrintJob:
    """Queue another receipt for an application, unless one is still waiting to print.

    The caller holds a lock on the application row, so two requests cannot both get through.
    """
    waiting = db.scalar(
        select(PrintJob.id)
        .where(
            PrintJob.application_id == application_id,
            PrintJob.status_event_id.is_(None),
            PrintJob.state == JobState.PENDING,
        )
        .limit(1)
    )
    if waiting is not None:
        raise AppError("REPRINT_PENDING", "A reprint for this application is already queued", 409)
    return enqueue(db, receipt, application_id=application_id)


def to_receipt(job: PrintJob) -> Receipt:
    return Receipt(id=job.id, **job.payload)


def claim_next(db: Session, device: Device) -> PrintJob | None:
    """Claim the oldest job that is pending or whose lease has run out."""
    settings = get_settings()
    now = datetime.now(UTC)
    lease_expired = now - timedelta(seconds=settings.lease_seconds)
    claimable = (
        select(PrintJob)
        .where(
            or_(
                PrintJob.state == JobState.PENDING,
                and_(PrintJob.state == JobState.CLAIMED, PrintJob.claimed_at < lease_expired),
            )
        )
        .order_by(PrintJob.created_at)
        .limit(1)
        # A job another transaction is claiming right now is skipped, not waited for.
        .with_for_update(skip_locked=True)
    )

    while (job := db.scalar(claimable)) is not None:
        if job.attempts >= settings.max_attempts:
            # Abandoned on its last attempt.
            job.state = JobState.FAILED
            job.failure_reason = job.failure_reason or "lease_expired"
            db.flush()
            continue

        job.state = JobState.CLAIMED
        job.claimed_at = now
        job.device_id = device.id
        job.attempts += 1
        db.flush()
        return job
    return None


def _get_job(db: Session, job_id: uuid.UUID) -> PrintJob:
    job = db.scalar(select(PrintJob).where(PrintJob.id == job_id).with_for_update())
    if job is None:
        raise AppError("NOT_FOUND", "Print job not found", 404)
    return job


def ack(db: Session, job_id: uuid.UUID) -> PrintJob:
    """Mark the job printed. Safe to repeat: printing is at-least-once."""
    job = _get_job(db, job_id)
    if job.state != JobState.PRINTED:
        job.state = JobState.PRINTED
        job.printed_at = datetime.now(UTC)
        db.flush()
    return job


def fail(db: Session, job_id: uuid.UUID, reason: str) -> PrintJob:
    """Record a failed attempt: back to pending, or failed at the attempt limit."""
    job = _get_job(db, job_id)
    # Only a claimed job has an attempt to fail, so a repeated report changes nothing.
    if job.state == JobState.CLAIMED:
        job.failure_reason = reason
        at_limit = job.attempts >= get_settings().max_attempts
        job.state = JobState.FAILED if at_limit else JobState.PENDING
        db.flush()
    return job
