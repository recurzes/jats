import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.device import register_device
from app.auth.jwt import current_user
from app.db import get_db

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DeviceCreated(BaseModel):
    id: uuid.UUID
    name: str
    # Shown only in this response. Only its hash is stored.
    key: str


@router.post("", status_code=201)
def create_device(
    body: DeviceCreate,
    user_id: Annotated[uuid.UUID, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DeviceCreated:
    device, key = register_device(db, user_id, body.name)
    created = DeviceCreated(id=device.id, name=device.name, key=key)
    db.commit()
    return created
