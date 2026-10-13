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
