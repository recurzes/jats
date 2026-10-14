from collections.abc import Iterator
from typing import Any

import pytest
import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from app.config import get_settings
from app.errors import register_error_handlers
from app.sentry import before_send, init_sentry

EMAIL_TEXT = "Unfortunately we will not be moving forward with your application"
JWT = "eyJhbGciOiJFZERTQSJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlLXNpZ25hdHVyZQ"
AUTH_CODE = "4/0AbCdEfGhIjKlMnOpQrStUvWxYz"


@pytest.fixture
def sentry_events(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Sentry switched on, with the events it would send collected instead."""
    events: list[dict[str, Any]] = []

    class CollectingTransport(Transport):
        def capture_envelope(self, envelope: Envelope) -> None:
            event = envelope.get_event()
            if event is not None:
                events.append(event)

    monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.invalid/1")
    get_settings.cache_clear()
    original_init = sentry_sdk.init
    monkeypatch.setattr(
        sentry_sdk,
        "init",
        lambda **options: original_init(transport=CollectingTransport, **options),
    )
    try:
        assert init_sentry() is True
        yield events
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(None)
        get_settings.cache_clear()


def test_sentry_is_off_without_a_dsn() -> None:
    assert init_sentry() is False
    assert not sentry_sdk.is_initialized()


def test_before_send_strips_headers_bodies_and_the_query_string() -> None:
    event = {
        "request": {
            "method": "POST",
            "url": "http://testserver/crash",
            "query_string": f"code={AUTH_CODE}",
            "headers": {"authorization": f"Bearer {JWT}", "x-device-key": "abc"},
            "cookies": {"session": "abc"},
            "data": {"body": EMAIL_TEXT},
            "env": {"REMOTE_ADDR": "10.0.0.1"},
        },
        "logentry": {"message": f"Authorization: Bearer {JWT}"},
    }

    sent = before_send(event, {})

    assert sent["request"] == {"method": "POST", "url": "http://testserver/crash"}
    assert JWT not in str(sent)


def test_a_forced_error_is_reported_without_email_text_or_credentials(
    sentry_events: list[dict[str, Any]],
) -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/crash")
    def crash() -> None:
        body = EMAIL_TEXT  # a local variable, as the sync has while it classifies
        raise RuntimeError(f"forced error ({len(body)}), token {JWT}")

    response = TestClient(app, raise_server_exceptions=False).post(
        f"/crash?code={AUTH_CODE}",
        headers={"Authorization": f"Bearer {JWT}", "X-Device-Key": "jats_dk_abcdefgh"},
        json={"body": EMAIL_TEXT},
    )
    sentry_sdk.flush()

    assert response.status_code == 500
    assert len(sentry_events) == 1
    event = sentry_events[0]
    assert event["exception"]["values"][-1]["type"] == "RuntimeError"
    assert set(event["request"]) <= {"method", "url"}
    sent = str(event)
    assert "forced error" in sent
    for leaked in (EMAIL_TEXT, JWT, "jats_dk_abcdefgh", AUTH_CODE):
        assert leaked not in sent
