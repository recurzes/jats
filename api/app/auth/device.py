import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.printing.models import Device

DEVICE_KEY_PREFIX = "jats_dk_"


def generate_device_key() -> str:
    return DEVICE_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_device_key(key: str) -> str:
    # The key is already 32 random bytes, so a slow password hash would add nothing.
    return hashlib.sha256(key.encode()).hexdigest()


def verify_device_key(key: str, key_hash: str) -> bool:
    return hmac.compare_digest(hash_device_key(key), key_hash)


def require_device(
    db: Annotated[Session, Depends(get_db)],
    x_device_key: Annotated[str | None, Header()] = None,
) -> Device:
    device = None
    if x_device_key:
        device = db.scalar(select(Device).where(Device.key_hash == hash_device_key(x_device_key)))
    if device is None:
        raise AppError("DEVICE_AUTH", "Missing or invalid device key", 401)

    device.last_seen_at = datetime.now(UTC)
    db.commit()
    return device
