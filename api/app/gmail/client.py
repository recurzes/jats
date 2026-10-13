"""The Gmail adapter: the only module that calls the Gmail API."""

from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.crypto import decrypt
from app.gmail.models import GmailAccount

TOKEN_URI = "https://oauth2.googleapis.com/token"

# Gmail reports some quota errors as 403 instead of 429.
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded"}

# The first sync, and the fallback when the stored history id has expired.
RECENT_QUERY = "newer_than:7d"
IGNORED_LABELS = {"SPAM", "TRASH"}


class GmailError(Exception):
    """Any failure talking to Gmail."""


class GmailAuthError(GmailError):
    """The refresh token was revoked or has expired; the account has to be connected again."""


class GmailForbiddenError(GmailError):
    """Gmail refused the call, for example because the scope does not cover it."""


class GmailRateLimitError(GmailError):
    """Too many calls; try again later."""


class GmailServerError(GmailError):
    """Gmail failed on its side; try again later."""


class GmailHistoryExpiredError(GmailError):
    """The stored history id is too old for `history.list`; list recent mail instead."""


def _from_refresh_error(exc: RefreshError) -> GmailError:
    if "invalid_grant" in str(exc):
        return GmailAuthError("Gmail refused the stored refresh token (invalid_grant)")
    if exc.retryable:
        return GmailServerError("Google could not refresh the access token")
    return GmailError(f"Could not refresh the Gmail access token: {exc}")


def _from_http_error(exc: HttpError) -> GmailError | None:
    status = exc.status_code
    details = exc.error_details if isinstance(exc.error_details, list) else []
    reasons = {detail.get("reason") for detail in details if isinstance(detail, dict)}

    if status == 401:
        return GmailAuthError("Gmail rejected the access token (401)")
    if status == 429 or (status == 403 and reasons & RATE_LIMIT_REASONS):
        return GmailRateLimitError(f"Gmail rate limit reached ({status})")
    if status == 403:
        return GmailForbiddenError(f"Gmail refused the request (403): {exc.reason}")
    if status >= 500:
        return GmailServerError(f"Gmail server error ({status})")
    return None


def execute(request: Any) -> Any:
    """Run a Gmail API request, turning 401, 403, 429 and 5xx answers into typed errors.

    Other HTTP errors, such as a 404, are raised unchanged.
    """
    try:
        return request.execute()
    except RefreshError as exc:
        raise _from_refresh_error(exc) from None
    except HttpError as exc:
        error = _from_http_error(exc)
        if error is None:
            raise
        raise error from None


def build_service(credentials: Credentials) -> Any:
    # The discovery document ships with the library, so this makes no network call.
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def get_gmail_service(account: GmailAccount) -> Any:
    """Build a Gmail service from the account's stored refresh token."""
    settings = get_settings()
    credentials = Credentials(
        token=None,
        refresh_token=decrypt(account.refresh_token_enc),
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    # Get the access token now, so a revoked refresh token fails here and not mid-sync.
    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        raise _from_refresh_error(exc) from None
    return build_service(credentials)


def get_email_address(service: Any) -> str:
    return execute(service.users().getProfile(userId="me"))["emailAddress"]


def get_current_history_id(service: Any) -> str:
    """The mailbox's newest history id: the bookmark an incremental sync starts from."""
    return str(execute(service.users().getProfile(userId="me"))["historyId"])


def list_message_ids(service: Any, query: str = RECENT_QUERY) -> list[str]:
    """Ids of every message matching the query, newest first. Gmail leaves out spam and trash."""
    ids: list[str] = []
    page_token = None
    while True:
        page = execute(service.users().messages().list(userId="me", q=query, pageToken=page_token))
        ids.extend(message["id"] for message in page.get("messages", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return ids


def list_new_message_ids_since(service: Any, history_id: str) -> tuple[list[str], str]:
    """Ids of the messages added after `history_id`, oldest first, and the newest history id."""
    ids: dict[str, None] = {}  # a dict, to drop repeats and keep the order
    newest = history_id
    page_token = None
    while True:
        request = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=history_id,
                historyTypes=["messageAdded"],
                pageToken=page_token,
            )
        )
        try:
            page = execute(request)
        except HttpError as exc:
            if exc.status_code == 404:
                raise GmailHistoryExpiredError("The stored Gmail history id expired") from None
            raise
        for record in page.get("history", []):
            for added in record.get("messagesAdded", []):
                message = added["message"]
                if not IGNORED_LABELS & set(message.get("labelIds", [])):
                    ids[message["id"]] = None
        newest = str(page.get("historyId", newest))
        page_token = page.get("nextPageToken")
        if not page_token:
            return list(ids), newest


def get_message(service: Any, message_id: str) -> dict[str, Any] | None:
    """The full message, or None when it was deleted after it was listed."""
    request = service.users().messages().get(userId="me", id=message_id, format="full")
    try:
        return execute(request)
    except HttpError as exc:
        if exc.status_code == 404:
            return None
        raise
