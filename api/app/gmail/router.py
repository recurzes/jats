import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.jwt import current_user
from app.auth.oauth_state import read_state
from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.gmail import oauth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["gmail"])


class ConnectUrl(BaseModel):
    url: str


def _back_to_frontend(result: str) -> RedirectResponse:
    frontend_url = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(f"{frontend_url}/?gmail={result}", status_code=302)


@router.get("/start")
def start(user_id: Annotated[uuid.UUID, Depends(current_user)]) -> ConnectUrl:
    # JSON instead of a redirect: a browser redirect could not carry the Authorization header.
    return ConnectUrl(url=oauth.authorization_url(user_id))


@router.get("/callback")
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
