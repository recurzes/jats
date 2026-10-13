import logging
import uuid
from datetime import UTC, datetime

from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.oauth_state import make_state
from app.config import get_settings
from app.crypto import encrypt
from app.errors import AppError
from app.gmail.client import TOKEN_URI, build_service, get_email_address
from app.gmail.models import AccountState, GmailAccount

logger = logging.getLogger(__name__)

# Read-only, so a bug can never delete or send mail.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"

REQUIRED_SETTINGS = ("google_client_id", "google_client_secret", "state_secret", "token_enc_key")


def require_config() -> None:
    """Refuse to start a connect flow that could not finish."""
    settings = get_settings()
    missing = [name.upper() for name in REQUIRED_SETTINGS if not getattr(settings, name)]
    if missing:
        logger.error("Gmail connect is not configured; missing %s", ", ".join(missing))
        raise AppError("GMAIL_CONFIG", "The Gmail connection is not configured", 503)


def _flow() -> Flow:
    settings = get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
        }
    }
    # No PKCE: the callback is a separate request with nowhere to keep the code verifier, and
    # the client secret already protects the code exchange.
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
        autogenerate_code_verifier=False,
    )


def authorization_url(user_id: uuid.UUID) -> str:
    """The Google consent URL for this user."""
    require_config()
    url, _ = _flow().authorization_url(
        # offline + consent make Google return a refresh token every time, not only the first.
        access_type="offline",
        prompt="consent",
        state=make_state(user_id),
    )
    return url


def exchange_code(code: str) -> tuple[str, str]:
    """Swap the Google code for `(refresh_token, email_address)`."""
    flow = _flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    if not credentials.refresh_token:
        raise RuntimeError("Google returned no refresh token")
    return credentials.refresh_token, get_email_address(build_service(credentials))


def save_account(
    db: Session, user_id: uuid.UUID, email_address: str, refresh_token: str
) -> GmailAccount:
    """Create the user's Gmail account, or replace it when one is already connected."""
    account = db.scalar(select(GmailAccount).where(GmailAccount.user_id == user_id))
    if account is None:
        account = GmailAccount(user_id=user_id)
        db.add(account)
    elif account.email_address != email_address:
        # A history id only means something inside the mailbox it came from.
        account.history_id = None

    account.email_address = email_address
    account.refresh_token_enc = encrypt(refresh_token)
    account.state = AccountState.OK
    account.last_error = None
    account.connected_at = datetime.now(UTC)
    db.flush()
    return account
