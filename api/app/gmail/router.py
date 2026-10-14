import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.jwt import current_user
from app.auth.oauth_state import read_state
from app.config import get_settings
from app.db import get_db
from app.errors import AppError, error_responses
from app.gmail import oauth, sync
from app.gmail.models import AccountState, SyncTrigger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["gmail"])
sync_router = APIRouter(tags=["gmail"])


class ConnectUrl(BaseModel):
    url: str


class SyncStarted(BaseModel):
    status: str = "started"


def _back_to_frontend(result: str) -> RedirectResponse:
    frontend_url = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(f"{frontend_url}/?gmail={result}", status_code=302)


@router.get("/start", summary="Begin connecting Gmail", responses=error_responses(401, 403, 503))
def start(user_id: Annotated[uuid.UUID, Depends(current_user)]) -> ConnectUrl:
    # JSON instead of a redirect: a browser redirect could not carry the Authorization header.
    return ConnectUrl(url=oauth.authorization_url(user_id))


@router.get(
    "/callback",
    summary="Finish connecting Gmail",
    status_code=302,
    response_class=RedirectResponse,
    responses={
        302: {"description": "Back to the web app, with `?gmail=connected` or `?gmail=error`"},
        **error_responses(422),
    },
)
def callback(
    db: Annotated[Session, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Public: Google sends the browser here, so the signed state is the only protection.

    The browser is mid-navigation, so every failure goes back to the web app instead of
    answering with a JSON error.
    """
    try:
        user_id = read_state(state or "")
    except AppError:
        logger.warning("Gmail connect failed: invalid or expired state")
        return _back_to_frontend("error")

    if error or not code:
        # For example access_denied, when consent was cancelled.
        logger.warning("Gmail connect failed: Google answered %r", error or "no code")
        return _back_to_frontend("error")

    try:
        refresh_token, email_address = oauth.exchange_code(code)
        oauth.save_account(db, user_id, email_address, refresh_token)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Gmail connect failed while exchanging the code or saving the account")
        return _back_to_frontend("error")

    logger.info("Gmail account connected")
    return _back_to_frontend("connected")


@sync_router.post(
    "/sync",
    status_code=202,
    summary="Run a Gmail sync now",
    responses=error_responses(401, 403, 409),
)
def start_sync(
    user_id: Annotated[uuid.UUID, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> SyncStarted:
    """Run a Gmail sync now, without waiting for the scheduler. The sync itself runs after the
    response, and its outcome is a `sync_runs` row."""
    account = sync.find_account(db, user_id)
    if account is None:
        raise AppError("GMAIL_NOT_CONNECTED", "No Gmail account is connected", 409)
    if account.state != AccountState.OK:
        raise AppError("GMAIL_NEEDS_REAUTH", "Gmail has to be connected again", 409)

    background_tasks.add_task(sync.sync_owner_account, SyncTrigger.MANUAL)
    return SyncStarted()
