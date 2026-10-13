import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, register_error_handlers
from app.logging import REQUEST_ID_HEADER, RequestIdMiddleware


@pytest.fixture
def error_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    @app.get("/app-error")
    def raise_app_error() -> None:
        raise AppError("DEVICE_AUTH", "Bad device key", 401)

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("secret detail")

    @app.get("/items/{item_id}")
    def read_item(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    return TestClient(app, raise_server_exceptions=False)


def test_app_error_returns_code_message_and_status(error_client: TestClient) -> None:
    response = error_client.get("/app-error")

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "DEVICE_AUTH", "message": "Bad device key"}}


def test_unknown_route_uses_the_error_shape(error_client: TestClient) -> None:
    response = error_client.get("/nope")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}


def test_validation_error_uses_the_error_shape(error_client: TestClient) -> None:
    response = error_client.get("/items/abc")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"
    assert "item_id" in response.json()["error"]["message"]


def test_unexpected_error_is_logged_and_returns_generic_500(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        response = error_client.get("/crash")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL", "message": "Internal server error"}}
    assert response.headers[REQUEST_ID_HEADER]
    assert "secret detail" not in response.text
    assert any(record.exc_info for record in caplog.records)
