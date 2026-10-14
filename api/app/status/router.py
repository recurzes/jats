import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.jwt import current_user
from app.db import get_db
from app.errors import error_responses
from app.status import service
from app.status.schemas import SystemStatus

router = APIRouter(tags=["status"], responses=error_responses(401, 403))


@router.get("/status", summary="Read the state of the pipeline")
def get_status(
    user_id: Annotated[uuid.UUID, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SystemStatus:
    """The last sync, the Gmail connection, the printer and the print queue."""
    return service.read_status(db, user_id)
