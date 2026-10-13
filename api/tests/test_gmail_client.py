import json
from typing import Any

import httplib2
import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.crypto import encrypt
from app.gmail import client
from app.gmail.client import (
    GmailAuthError,
    GmailError,
    GmailForbiddenError,
    GmailRateLimitError,
    GmailServerError,
    execute,
    get_email_address,
    get_gmail_service,
)
from app.gmail.models import GmailAccount

REFRESH_TOKEN = "1//refresh-token-value"


class FakeRequest:
    """A Gmail API request that answers with a value or raises an error."""

    def __init__(self, result: Any) -> None:
        self.result = result

    def execute(self) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def http_error(status: int, reason: str | None = None) -> HttpError:
    errors = [{"reason": reason, "message": "nope"}] if reason else []
    body = {"error": {"code": status, "message": "nope", "errors": errors}}
    return HttpError(httplib2.Response({"status": status}), json.dumps(body).encode())


def account() -> GmailAccount:
    return GmailAccount(email_address="me@example.com", refresh_token_enc=encrypt(REFRESH_TOKEN))


def test_execute_returns_the_answer() -> None:
    answer = {"emailAddress": "me@example.com"}

    assert execute(FakeRequest(answer)) == answer


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (http_error(401), GmailAuthError),
        (http_error(403, "insufficientPermissions"), GmailForbiddenError),
        (http_error(403), GmailForbiddenError),
        (http_error(403, "rateLimitExceeded"), GmailRateLimitError),
        (http_error(403, "userRateLimitExceeded"), GmailRateLimitError),
        (http_error(429), GmailRateLimitError),
        (http_error(500), GmailServerError),
        (http_error(503), GmailServerError),
    ],
)
def test_execute_maps_http_errors(error: HttpError, expected: type[GmailError]) -> None:
    with pytest.raises(GmailError) as raised:
        execute(FakeRequest(error))

    assert type(raised.value) is expected


def test_execute_leaves_other_http_errors_alone() -> None:
    # A 404 from history.list means the history id expired; the sync handles that itself.
    with pytest.raises(HttpError) as raised:
        execute(FakeRequest(http_error(404)))

    assert raised.value.status_code == 404


def test_execute_maps_invalid_grant_to_auth_error() -> None:
    # The access token is refreshed inside a request once it has expired.
    error = RefreshError("invalid_grant: Token has been expired or revoked.")

    with pytest.raises(GmailAuthError):
        execute(FakeRequest(error))


def test_get_gmail_service_uses_the_decrypted_token(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Credentials] = []

    def refresh(self: Credentials, request: object) -> None:
        self.token = "access-token"

    def build_service(credentials: Credentials) -> str:
        seen.append(credentials)
        return "service"

    monkeypatch.setattr(Credentials, "refresh", refresh)
    monkeypatch.setattr(client, "build_service", build_service)

    assert get_gmail_service(account()) == "service"
    credentials = seen[0]
    assert credentials.refresh_token == REFRESH_TOKEN
    assert credentials.token == "access-token"
    assert credentials.client_id == get_settings().google_client_id
    assert credentials.client_secret == get_settings().google_client_secret
    assert credentials.token_uri == "https://oauth2.googleapis.com/token"


def test_get_gmail_service_raises_auth_error_on_invalid_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refresh(self: Credentials, request: object) -> None:
        raise RefreshError(
            "invalid_grant: Token has been expired or revoked.",
            {"error": "invalid_grant", "error_description": "Token has been expired or revoked."},
        )

    monkeypatch.setattr(Credentials, "refresh", refresh)

    with pytest.raises(GmailAuthError) as raised:
        get_gmail_service(account())

    assert REFRESH_TOKEN not in str(raised.value)


def test_get_gmail_service_does_not_ask_for_reauth_on_other_refresh_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refresh(self: Credentials, request: object) -> None:
        raise RefreshError("invalid_client: Unauthorized", {"error": "invalid_client"})

    monkeypatch.setattr(Credentials, "refresh", refresh)

    with pytest.raises(GmailError) as raised:
        get_gmail_service(account())

    assert type(raised.value) is GmailError


def test_build_service_makes_a_gmail_service_offline() -> None:
    service = client.build_service(Credentials(token="access-token"))

    request = service.users().getProfile(userId="me")
    assert request.uri == "https://gmail.googleapis.com/gmail/v1/users/me/profile?alt=json"


def test_get_email_address() -> None:
    class Service:
        def users(self) -> "Service":
            return self

        def getProfile(self, userId: str) -> FakeRequest:  # noqa: N802, N803
            assert userId == "me"
            return FakeRequest({"emailAddress": "me@example.com"})

    assert get_email_address(Service()) == "me@example.com"
