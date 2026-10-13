import json
import logging
import uuid
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from fastapi.testclient import TestClient
from requests.adapters import HTTPAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.oauth_state import make_state, read_state
from app.config import get_settings
from app.crypto import decrypt
from app.gmail import oauth
from app.gmail.models import AccountState, GmailAccount

REFRESH_TOKEN = "1//refresh-token-value"
CONNECTED = "http://localhost:5173/?gmail=connected"
ERROR = "http://localhost:5173/?gmail=error"


@pytest.fixture
def owner_id() -> uuid.UUID:
    return get_settings().owner_user_id


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stand in for Google's code exchange; returns the codes it was asked to exchange."""
    codes: list[str] = []

    def exchange_code(code: str) -> tuple[str, str]:
        codes.append(code)
        return REFRESH_TOKEN, "me@example.com"

    monkeypatch.setattr(oauth, "exchange_code", exchange_code)
    return codes


def callback(client: TestClient, **params: str):
    return client.get("/auth/google/callback", params=params, follow_redirects=False)


def assert_redirect(response, location: str) -> None:
    assert response.status_code == 302
    assert response.headers["location"] == location


# --- GET /auth/google/start


def test_start_returns_the_google_consent_url(
    client: TestClient, auth_headers: dict[str, str], owner_id: uuid.UUID
) -> None:
    response = client.get("/auth/google/start", headers=auth_headers)

    assert response.status_code == 200
    assert set(response.json()) == {"url"}
    url = urlsplit(response.json()["url"])
    query = {name: values[0] for name, values in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://accounts.google.com/o/oauth2/auth"
    assert query["response_type"] == "code"
    assert query["client_id"] == "test-client.apps.googleusercontent.com"
    assert query["redirect_uri"] == "http://localhost:8000/auth/google/callback"
    assert query["scope"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert query["access_type"] == "offline"
    assert query["prompt"] == "consent"
    assert read_state(query["state"]) == owner_id
    # The callback could not supply a PKCE verifier, so no challenge may be sent.
    assert "code_challenge" not in query


def test_start_needs_a_token(client: TestClient) -> None:
    response = client.get("/auth/google/start")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_start_is_owner_only(client: TestClient, make_token: Callable[..., str]) -> None:
    headers = {"Authorization": f"Bearer {make_token(sub=uuid.uuid4())}"}

    response = client.get("/auth/google/start", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_OWNER"


@pytest.mark.parametrize(
    "setting", ["google_client_id", "google_client_secret", "state_secret", "token_enc_key"]
)
def test_start_refuses_when_not_configured(
    setting: str,
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), setting, "")

    response = client.get("/auth/google/start", headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GMAIL_CONFIG"


# --- GET /auth/google/callback


def test_callback_stores_the_encrypted_token(
    client: TestClient, db: Session, google: list[str], owner_id: uuid.UUID
) -> None:
    # No Authorization header: Google redirects the browser here.
    response = callback(client, code="the-code", state=make_state(owner_id))

    assert_redirect(response, CONNECTED)
    assert google == ["the-code"]
    account = db.scalars(select(GmailAccount)).one()
    assert account.user_id == owner_id
    assert account.email_address == "me@example.com"
    assert account.state == AccountState.OK
    assert account.last_error is None
    assert account.history_id is None
    assert REFRESH_TOKEN not in account.refresh_token_enc
    assert decrypt(account.refresh_token_enc) == REFRESH_TOKEN


def test_reconnecting_replaces_the_account_and_clears_needs_reauth(
    client: TestClient, db: Session, google: list[str], owner_id: uuid.UUID
) -> None:
    old = GmailAccount(
        user_id=owner_id,
        email_address="me@example.com",
        refresh_token_enc="old",
        history_id="12345",
        state=AccountState.NEEDS_REAUTH,
        last_error="invalid_grant",
    )
    db.add(old)
    db.commit()

    response = callback(client, code="the-code", state=make_state(owner_id))

    assert_redirect(response, CONNECTED)
    account = db.scalars(select(GmailAccount)).one()
    assert account.id == old.id
    assert account.state == AccountState.OK
    assert account.last_error is None
    assert decrypt(account.refresh_token_enc) == REFRESH_TOKEN
    # Same mailbox, so the sync can carry on from where it stopped.
    assert account.history_id == "12345"


def test_connecting_another_mailbox_resets_the_history_id(
    client: TestClient, db: Session, google: list[str], owner_id: uuid.UUID
) -> None:
    db.add(
        GmailAccount(
            user_id=owner_id,
            email_address="old@example.com",
            refresh_token_enc="old",
            history_id="12345",
        )
    )
    db.commit()

    callback(client, code="the-code", state=make_state(owner_id))

    account = db.scalars(select(GmailAccount)).one()
    assert account.email_address == "me@example.com"
    assert account.history_id is None


@pytest.mark.parametrize("state", [None, "", "garbage"])
def test_callback_with_a_bad_state_stores_nothing(
    state: str | None, client: TestClient, db: Session, google: list[str]
) -> None:
    params = {"code": "the-code"} | ({} if state is None else {"state": state})

    response = callback(client, **params)

    assert_redirect(response, ERROR)
    assert google == []
    assert db.scalars(select(GmailAccount)).all() == []


def test_callback_when_consent_was_denied(
    client: TestClient, db: Session, google: list[str], owner_id: uuid.UUID
) -> None:
    response = callback(client, error="access_denied", state=make_state(owner_id))

    assert_redirect(response, ERROR)
    assert google == []
    assert db.scalars(select(GmailAccount)).all() == []


def test_callback_when_the_code_exchange_fails(
    client: TestClient, db: Session, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exchange_code(code: str) -> tuple[str, str]:
        raise RuntimeError("(invalid_grant) Bad Request")

    monkeypatch.setattr(oauth, "exchange_code", exchange_code)

    response = callback(client, code="used-code", state=make_state(owner_id))

    assert_redirect(response, ERROR)
    assert db.scalars(select(GmailAccount)).all() == []


def test_callback_never_logs_the_refresh_token(
    client: TestClient, google: list[str], owner_id: uuid.UUID, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        callback(client, code="the-code", state=make_state(owner_id))

    assert REFRESH_TOKEN not in caplog.text


# --- exchange_code


class TokenEndpoint:
    """Google's token endpoint: records what it was sent and answers with `tokens`."""

    def __init__(self, tokens: dict[str, object]) -> None:
        self.tokens = tokens
        self.calls: list[tuple[str, dict[str, str]]] = []

    def send(self, request: requests.PreparedRequest) -> requests.Response:
        form = {name: values[0] for name, values in parse_qs(str(request.body)).items()}
        self.calls.append((str(request.url), form))
        response = requests.Response()
        response.status_code = 200
        response.request = request
        response._content = json.dumps(self.tokens).encode()
        return response


def test_exchange_code_returns_the_refresh_token_and_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = TokenEndpoint(
        {
            "access_token": "access-token",
            "refresh_token": REFRESH_TOKEN,
            "expires_in": 3599,
            "scope": oauth.SCOPES[0],
            "token_type": "Bearer",
        }
    )
    # Replaced at the transport, so nothing can reach the network.
    monkeypatch.setattr(HTTPAdapter, "send", lambda adapter, request, **_: endpoint.send(request))
    monkeypatch.setattr(oauth, "get_email_address", lambda service: "me@example.com")

    assert oauth.exchange_code("the-code") == (REFRESH_TOKEN, "me@example.com")
    url, data = endpoint.calls[0]
    assert url == "https://oauth2.googleapis.com/token"
    assert data["code"] == "the-code"
    assert data["grant_type"] == "authorization_code"
    assert data["redirect_uri"] == "http://localhost:8000/auth/google/callback"
    assert "code_verifier" not in data


def test_exchange_code_fails_without_a_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = TokenEndpoint(
        {
            "access_token": "access-token",
            "expires_in": 3599,
            "scope": oauth.SCOPES[0],
            "token_type": "Bearer",
        }
    )
    # Replaced at the transport, so nothing can reach the network.
    monkeypatch.setattr(HTTPAdapter, "send", lambda adapter, request, **_: endpoint.send(request))

    with pytest.raises(RuntimeError, match="no refresh token"):
        oauth.exchange_code("the-code")
