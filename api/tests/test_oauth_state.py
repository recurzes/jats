import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.oauth_state import ALGORITHM, make_state, read_state
from app.config import get_settings
from app.errors import AppError


def assert_rejected(token: str) -> None:
    with pytest.raises(AppError) as raised:
        read_state(token)
    assert raised.value.code == "OAUTH_STATE"
    assert raised.value.status == 400


def sign(secret: str | None = None, **claims: object) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "nonce": "n",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
        **claims,
    }
    return jwt.encode(payload, secret or get_settings().state_secret, algorithm=ALGORITHM)


def test_valid_state_returns_the_user_id() -> None:
    user_id = uuid.uuid4()

    assert read_state(make_state(user_id)) == user_id


def test_each_state_is_different() -> None:
    user_id = uuid.uuid4()

    assert make_state(user_id) != make_state(user_id)


def test_state_expires_after_ten_minutes() -> None:
    claims = jwt.decode(make_state(uuid.uuid4()), options={"verify_signature": False})
    lifetime = claims["exp"] - datetime.now(UTC).timestamp()

    assert 590 < lifetime <= 600


def test_expired_state_is_rejected() -> None:
    assert_rejected(sign(exp=datetime.now(UTC) - timedelta(seconds=1)))


def test_tampered_state_is_rejected() -> None:
    header, _, signature = make_state(uuid.uuid4()).split(".")
    other_payload = make_state(uuid.uuid4()).split(".")[1]

    assert_rejected(f"{header}.{other_payload}.{signature}")


def test_state_signed_with_another_secret_is_rejected() -> None:
    assert_rejected(sign(secret="another-secret-that-is-also-long-enough-x"))


def test_unsigned_state_is_rejected() -> None:
    payload = {"sub": str(uuid.uuid4()), "nonce": "n", "exp": 9999999999}

    assert_rejected(jwt.encode(payload, None, algorithm="none"))


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c"])
def test_malformed_state_is_rejected(token: str) -> None:
    assert_rejected(token)


def test_state_without_a_user_id_is_rejected() -> None:
    assert_rejected(sign(sub="not-a-uuid"))


def test_state_without_an_expiry_is_rejected() -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "nonce": "n"}, get_settings().state_secret, algorithm=ALGORITHM
    )

    assert_rejected(token)


def test_empty_secret_signs_and_accepts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    token = make_state(uuid.uuid4())
    monkeypatch.setattr(get_settings(), "state_secret", "")

    assert_rejected(token)
    with pytest.raises(AppError):
        make_state(uuid.uuid4())
