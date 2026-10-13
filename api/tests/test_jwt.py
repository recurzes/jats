import base64
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.auth.jwt import verify_token
from app.config import get_settings
from app.errors import AppError

# Any route behind current_user works here.
USER_URL = "/devices"
BODY = {"name": "desk-esp32"}


def post(client: TestClient, token: str):
    return client.post(USER_URL, json=BODY, headers={"Authorization": f"Bearer {token}"})


def assert_auth_invalid(response) -> None:
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_verify_token_returns_the_user_id(make_token: Callable[..., str]) -> None:
    user_id = uuid.uuid4()

    assert verify_token(make_token(sub=user_id)) == user_id


def test_valid_owner_token_is_accepted(client: TestClient, make_token: Callable[..., str]) -> None:
    assert post(client, make_token()).status_code == 201


def test_missing_token_returns_401(client: TestClient) -> None:
    assert_auth_invalid(client.post(USER_URL, json=BODY))


def test_non_bearer_header_returns_401(client: TestClient) -> None:
    assert_auth_invalid(client.post(USER_URL, json=BODY, headers={"Authorization": "Basic abc"}))


def test_garbage_token_returns_401(client: TestClient) -> None:
    assert_auth_invalid(post(client, "not-a-jwt"))


def test_expired_token_returns_401(client: TestClient, make_token: Callable[..., str]) -> None:
    token = make_token(exp=datetime.now(UTC) - timedelta(minutes=1))

    assert_auth_invalid(post(client, token))


def test_tampered_token_returns_401(client: TestClient, make_token: Callable[..., str]) -> None:
    # Another user's token, with the payload swapped for one naming the owner.
    header, payload, signature = make_token(sub=uuid.uuid4()).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = str(get_settings().owner_user_id)
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()

    assert_auth_invalid(post(client, f"{header}.{forged}.{signature}"))


def test_token_signed_with_another_key_returns_401(
    client: TestClient, make_token: Callable[..., str]
) -> None:
    token = make_token(key=Ed25519PrivateKey.generate())

    assert_auth_invalid(post(client, token))


def test_token_signed_with_a_shared_secret_returns_401(
    client: TestClient, make_token: Callable[..., str]
) -> None:
    token = make_token(key="a-shared-secret-that-is-long-enough-for-hs256", algorithm="HS256")

    assert_auth_invalid(post(client, token))


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "https://ep-other.neonauth.example.com"},
        {"iss": "https://ep-other.neonauth.example.com"},
        # The full Neon Auth URL is not the issuer; only its origin is.
        {"iss": "https://ep-test.neonauth.example.com/neondb/auth"},
        {"sub": "not-a-uuid"},
    ],
)
def test_wrong_claims_return_401(
    client: TestClient, make_token: Callable[..., str], claims: dict[str, str]
) -> None:
    assert_auth_invalid(post(client, make_token(**claims)))


def test_unreachable_signing_keys_return_401(
    client: TestClient, make_token: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(self: jwt.PyJWKClient) -> None:
        raise jwt.PyJWKClientConnectionError("down")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fail)

    assert_auth_invalid(post(client, make_token()))


def test_no_neon_auth_url_refuses_every_token(
    client: TestClient, make_token: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    token = make_token()
    monkeypatch.setattr(get_settings(), "neon_auth_base_url", "")

    assert_auth_invalid(post(client, token))


def test_another_valid_user_returns_403(client: TestClient, make_token: Callable[..., str]) -> None:
    response = post(client, make_token(sub=uuid.uuid4()))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_OWNER"


def test_verify_token_raises_app_error() -> None:
    with pytest.raises(AppError) as error:
        verify_token("not-a-jwt")

    assert error.value.status == 401
