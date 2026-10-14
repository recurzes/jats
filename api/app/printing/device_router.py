import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.device import require_device
from app.db import get_db
from app.errors import error_responses
from app.printing import queue
from app.printing.models import Device, JobState, PrintJob
from app.printing.receipt import Receipt

router = APIRouter(
    prefix="/device",
    tags=["device"],
    dependencies=[Depends(require_device)],
    responses=error_responses(401, 422),
)

FailureReason = Literal["bt_connect", "out_of_paper", "print_error", "other"]


class FailRequest(BaseModel):
    reason: FailureReason


class JobStatus(BaseModel):
    id: uuid.UUID
    state: JobState


def job_status(job: PrintJob) -> JobStatus:
    return JobStatus(id=job.id, state=job.state)


@router.get(
    "/jobs/next",
    response_model=Receipt,
    summary="Claim the next print job",
    responses={204: {"description": "No job is waiting"}},
)
def claim_next_job(
    device: Annotated[Device, Depends(require_device)],
    db: Annotated[Session, Depends(get_db)],
) -> Receipt | Response:
    job = queue.claim_next(db, device)
    receipt = queue.to_receipt(job) if job else None
    # Also saves any job the claim marked failed.
    db.commit()
    return receipt or Response(status_code=204)


@router.post("/jobs/{job_id}/ack", summary="Mark a job printed", responses=error_responses(404))
def ack_job(job_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> JobStatus:
    status = job_status(queue.ack(db, job_id))
    db.commit()
    return status


@router.post("/jobs/{job_id}/fail", summary="Report a failed print", responses=error_responses(404))
def fail_job(
    job_id: uuid.UUID, body: FailRequest, db: Annotated[Session, Depends(get_db)]
) -> JobStatus:
    status = job_status(queue.fail(db, job_id, body.reason))
    db.commit()
    return status
