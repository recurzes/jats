import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.device import DEVICE_KEY_PREFIX, verify_device_key
from app.config import get_settings
from app.printing.models import Device


def test_create_device_returns_the_key_and_stores_only_the_hash(
    client: TestClient, auth_headers: dict[str, str], db: Session
) -> None:
    response = client.post("/devices", json={"name": "desk-esp32"}, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "key"}
    assert body["name"] == "desk-esp32"
    assert body["key"].startswith(DEVICE_KEY_PREFIX)

    device = db.scalars(select(Device)).one()
    assert str(device.id) == body["id"]
    assert device.user_id == get_settings().owner_user_id
    assert device.key_hash != body["key"]
    assert verify_device_key(body["key"], device.key_hash)


def test_created_key_works_on_the_device_endpoints(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    key = client.post("/devices", json={"name": "desk-esp32"}, headers=auth_headers).json()["key"]

    response = client.get("/device/jobs/next", headers={"X-Device-Key": key})

    assert response.status_code == 204


def test_each_device_gets_its_own_key(client: TestClient, auth_headers: dict[str, str]) -> None:
    first = client.post("/devices", json={"name": "one"}, headers=auth_headers).json()
    second = client.post("/devices", json={"name": "two"}, headers=auth_headers).json()

    assert first["key"] != second["key"]
    assert first["id"] != second["id"]


def test_create_device_without_a_token_creates_nothing(client: TestClient, db: Session) -> None:
    response = client.post("/devices", json={"name": "desk-esp32"})

    assert response.status_code == 401
    assert db.scalars(select(Device)).all() == []


def test_create_device_as_another_user_creates_nothing(
    client: TestClient, make_token: Callable[..., str], db: Session
) -> None:
    headers = {"Authorization": f"Bearer {make_token(sub=uuid.uuid4())}"}

    response = client.post("/devices", json={"name": "desk-esp32"}, headers=headers)

    assert response.status_code == 403
    assert db.scalars(select(Device)).all() == []


def test_create_device_rejects_a_bad_name(client: TestClient, auth_headers: dict[str, str]) -> None:
    for name in ("", "x" * 101):
        response = client.post("/devices", json={"name": name}, headers=auth_headers)

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION"
