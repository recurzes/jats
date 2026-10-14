from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.gmail.models import SyncResult, SyncTrigger


class LastSync(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    # Both empty while the sync is still running.
    finished_at: datetime | None
    result: SyncResult | None
    trigger: SyncTrigger
    error: str | None


class GmailState(StrEnum):
    OK = "ok"
    NEEDS_REAUTH = "needs_reauth"
    NOT_CONNECTED = "not_connected"


class GmailStatus(BaseModel):
    state: GmailState
    # Empty while no account is connected.
    address: str | None


class DeviceStatus(BaseModel):
    # Empty while no device has ever polled.
    last_seen_at: datetime | None
    # Seen within the last 2 minutes.
    online: bool


class QueueStatus(BaseModel):
    pending: int
    failed: int


class SystemStatus(BaseModel):
    """What the status strip shows."""

    # Empty before the first sync.
    last_sync: LastSync | None
    gmail: GmailStatus
    device: DeviceStatus
    queue: QueueStatus
    # Emails the classifier gave up on.
    failed_classifications: int
