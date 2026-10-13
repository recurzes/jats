import logging
import uuid
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import AppError

logger = logging.getLogger(__name__)

# Asymmetric only, so a token signed with a shared secret can never pass.
ALGORITHMS = ["EdDSA"]

bearer = HTTPBearer(auto_error=False)


def issuer() -> str:
    """Neon Auth puts the origin of its URL, without the path, in both `iss` and `aud`."""
    url = urlsplit(get_settings().neon_auth_base_url)
    return f"{url.scheme}://{url.netloc}"


@lru_cache
def jwk_client() -> jwt.PyJWKClient:
    # Caches the key set, and fetches it again when a token names a key it has not seen.
    base_url = get_settings().neon_auth_base_url.rstrip("/")
    return jwt.PyJWKClient(base_url + "/.well-known/jwks.json")


def verify_token(token: str) -> uuid.UUID:
    """Return the user id (`sub`) of a valid Neon Auth token."""
    if not get_settings().neon_auth_base_url:
        logger.error("NEON_AUTH_BASE_URL is not set, so no access token can be checked")
        raise AppError("AUTH_INVALID", "Missing or invalid access token", 401)

    try:
        signing_key = jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=issuer(),
            issuer=issuer(),
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        return uuid.UUID(claims["sub"])
    except jwt.PyJWKClientConnectionError:
        logger.error("Could not fetch the Neon Auth signing keys", exc_info=True)
    except (jwt.PyJWTError, ValueError):
        pass
    raise AppError("AUTH_INVALID", "Missing or invalid access token", 401)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> uuid.UUID:
    if credentials is None:
        raise AppError("AUTH_INVALID", "Missing or invalid access token", 401)

    user_id = verify_token(credentials.credentials)
    if user_id != get_settings().owner_user_id:
        raise AppError("NOT_OWNER", "This account is not the owner", 403)
    return user_id
