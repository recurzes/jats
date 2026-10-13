import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.errors import AppError

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
STATE_TTL = timedelta(minutes=10)


def _secret() -> str:
    secret = get_settings().state_secret
    if not secret:
        # An empty secret would sign states anyone could forge.
        logger.error("STATE_SECRET is not set, so no OAuth state can be signed or checked")
        raise AppError("OAUTH_STATE", "Invalid or expired OAuth state", 400)
    return secret


def make_state(user_id: uuid.UUID) -> str:
    """Return a signed value that names the user and stops working after 10 minutes."""
    payload = {
        "sub": str(user_id),
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.now(UTC) + STATE_TTL,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def read_state(token: str) -> uuid.UUID:
    """Return the user id of a state made by `make_state`, or raise OAUTH_STATE."""
    secret = _secret()
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub", "nonce"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        raise AppError("OAUTH_STATE", "Invalid or expired OAuth state", 400) from None
