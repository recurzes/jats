import hashlib

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.device import (
    DEVICE_KEY_PREFIX,
    generate_device_key,
    hash_device_key,
    verify_device_key,
)
from app.printing.models import Device

DEVICE_URL = "/device/jobs/next"


def test_generate_device_key_is_prefixed_and_random() -> None:
    key = generate_device_key()

    assert key.startswith(DEVICE_KEY_PREFIX)
    # token_urlsafe(32) is 43 characters of base64.
    assert len(key) == len(DEVICE_KEY_PREFIX) + 43
    assert key != generate_device_key()


def test_hash_device_key_is_sha256_hex() -> None:
    assert hash_device_key("jats_dk_abc") == hashlib.sha256(b"jats_dk_abc").hexdigest()


def test_verify_device_key() -> None:
    key = generate_device_key()

    assert verify_device_key(key, hash_device_key(key))
    assert not verify_device_key(generate_device_key(), hash_device_key(key))


def test_missing_key_returns_401(client: TestClient) -> None:
    response = client.get(DEVICE_URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "DEVICE_AUTH"


def test_wrong_key_returns_401(client: TestClient, device: Device, db: Session) -> None:
    response = client.get(DEVICE_URL, headers={"X-Device-Key": generate_device_key()})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "DEVICE_AUTH"
    db.refresh(device)
    assert device.last_seen_at is None


def test_valid_key_is_accepted_and_updates_last_seen(
    client: TestClient, device: Device, device_headers: dict[str, str], db: Session
) -> None:
    assert device.last_seen_at is None

    response = client.get(DEVICE_URL, headers=device_headers)

    assert response.status_code == 204
    db.refresh(device)
    assert device.last_seen_at is not None
