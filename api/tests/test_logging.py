import io
import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.logging import REQUEST_ID_HEADER, build_handler


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    handler = build_handler(stream)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield stream
    finally:
        root.removeHandler(handler)


def test_health_logs_one_json_line_with_the_request_id(
    client: TestClient, log_stream: io.StringIO
) -> None:
    response = client.get("/health")

    lines = [json.loads(line) for line in log_stream.getvalue().splitlines()]
    request_lines = [line for line in lines if line["logger"] == "app.request"]
    assert len(request_lines) == 1
    line = request_lines[0]
    assert {"time", "level", "logger", "message"} <= line.keys()
    assert line["level"] == "INFO"
    assert line["message"].startswith("GET /health 200")
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_each_request_gets_its_own_request_id(client: TestClient) -> None:
    first = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first != second


def test_data_fields_sit_next_to_the_message(log_stream: io.StringIO) -> None:
    logger = logging.getLogger("app.test")
    logger.setLevel(logging.INFO)

    # A field cannot replace one of the line's own keys.
    logger.info("Gmail sync finished", extra={"data": {"result": "ok", "level": "x"}})

    line = json.loads(log_stream.getvalue().splitlines()[-1])
    assert line["message"] == "Gmail sync finished"
    assert line["result"] == "ok"
    assert line["level"] == "INFO"


JWT = "eyJhbGciOiJFZERTQSJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlLXNpZ25hdHVyZQ"
DEVICE_KEY = "jats_dk_Zm9vYmFyLWZvb2Jhci1mb29iYXItZm9vYmFy"
REFRESH_TOKEN = "1//0abcdefghijklmnopqrstuvwxyz"
AUTH_CODE = "4/0AbCdEfGhIjKlMnOpQrStUvWxYz"


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        (f"headers: Authorization: Bearer {JWT}", JWT),
        (f"{{'authorization': 'Bearer {JWT}'}}", JWT),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        (f"X-Device-Key: {DEVICE_KEY}", DEVICE_KEY),
        ("{'x-device-key': 'not-in-the-usual-format'}", "not-in-the-usual-format"),
        (f"a bare token {JWT} in a sentence", JWT),
        (f"claimed by {DEVICE_KEY}", DEVICE_KEY),
        (f"refresh_token={REFRESH_TOKEN}&x=1", REFRESH_TOKEN),
        (f"Google sent {REFRESH_TOKEN} back", REFRESH_TOKEN),
        (f"callback?code={AUTH_CODE}", AUTH_CODE),
        ("token ya29.a0AfH6SMBx-abc_def", "ya29.a0AfH6SMBx-abc_def"),
        ("key sk-proj-abcdefghijklmnopqrstuvwx", "sk-proj-abcdefghijklmnopqrstuvwx"),
        ('{"client_secret": "GOCSPX-abc123"}', "GOCSPX-abc123"),
        ("postgresql+psycopg://jats:hunter2@db.example/jats", "hunter2"),
        ("the provider got test-llm-key", "test-llm-key"),  # LLM_API_KEY in conftest.py
    ],
)
def test_secrets_come_out_masked(log_stream: io.StringIO, message: str, secret: str) -> None:
    logger = logging.getLogger("app.test")
    logger.setLevel(logging.INFO)

    # As an argument, as a data field, and inside a traceback.
    logger.info("Seen: %s", message, extra={"data": {"detail": message}})
    try:
        raise RuntimeError(message)
    except RuntimeError:
        logger.exception("Failed")

    output = log_stream.getvalue()
    assert secret not in output
    first, second = (json.loads(line) for line in output.splitlines())
    assert first["message"].startswith("Seen: ")
    assert "***" in first["message"]
    assert "***" in first["detail"]
    assert "RuntimeError" in second["exception"]
    assert "***" in second["exception"]


def test_a_secret_named_data_field_loses_its_value(log_stream: io.StringIO) -> None:
    logger = logging.getLogger("app.test")
    logger.setLevel(logging.INFO)

    logger.info(
        "Request", extra={"data": {"headers": {"X-Device-Key": "abc", "Accept": "*/*"}, "n": 3}}
    )

    line = json.loads(log_stream.getvalue().splitlines()[-1])
    assert line["headers"] == {"X-Device-Key": "***", "Accept": "*/*"}
    assert line["n"] == 3


def test_ordinary_lines_are_left_alone(log_stream: io.StringIO) -> None:
    logger = logging.getLogger("app.test")
    logger.setLevel(logging.INFO)
    message = "STATE_SECRET is not set, so no OAuth state can be signed; 3 tokens checked at 1/2"

    logger.info(message)

    assert json.loads(log_stream.getvalue().splitlines()[-1])["message"] == message


def test_a_request_never_logs_its_credentials(
    client: TestClient, log_stream: io.StringIO, auth_headers: dict[str, str], device_key: str
) -> None:
    client.get("/status", headers=auth_headers)
    client.get("/device/jobs/next", headers={"X-Device-Key": device_key})
    client.get(f"/auth/google/callback?code={AUTH_CODE}&state=bad", follow_redirects=False)

    output = log_stream.getvalue()
    assert "GET /status 200" in output
    assert auth_headers["Authorization"].removeprefix("Bearer ") not in output
    assert device_key not in output
    assert AUTH_CODE not in output
