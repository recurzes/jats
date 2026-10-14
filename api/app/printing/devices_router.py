import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.device import register_device
from app.auth.jwt import current_user
from app.db import get_db
from app.errors import error_responses

router = APIRouter(prefix="/devices", tags=["devices"], responses=error_responses(401, 403))


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DeviceCreated(BaseModel):
    id: uuid.UUID
    name: str
    # Shown only in this response. Only its hash is stored.
    key: str


@router.post("", status_code=201, summary="Create a device", responses=error_responses(422))
def create_device(
    body: DeviceCreate,
    user_id: Annotated[uuid.UUID, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DeviceCreated:
    """Register a printer device. Its key is in this response and cannot be read again."""
    device, key = register_device(db, user_id, body.name)
    created = DeviceCreated(id=device.id, name=device.name, key=key)
    db.commit()
    return created
