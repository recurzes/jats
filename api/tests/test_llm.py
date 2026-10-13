import logging

import pytest
from llm_fake import status_error, timeout_error, use_llm

from app.classifier import llm
from app.classifier.llm import (
    LLMAuthError,
    LLMError,
    LLMRejected,
    LLMUnavailable,
    chat_json,
    get_client,
)
from app.config import get_settings

EMAIL_TEXT = "Unfortunately we are moving forward with other candidates"


def test_client_is_built_from_the_settings() -> None:
    get_client.cache_clear()
    try:
        client = get_client()
    finally:
        get_client.cache_clear()

    assert str(client.base_url) == "http://llm.invalid/v1/"
    assert client.api_key == "test-llm-key"
    assert client.timeout == 30
    assert client.max_retries == 0


def test_chat_json_sends_both_messages_and_returns_the_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = use_llm(monkeypatch, '{"ok": true}')

    assert chat_json("system text", "user text") == '{"ok": true}'

    (call,) = fake.calls
    assert call["model"] == "test-model"
    assert call["messages"] == [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "user text"},
    ]
    assert call["response_format"] == {"type": "json_object"}
    assert fake.sleeps == []


def test_an_empty_answer_is_an_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    use_llm(monkeypatch, None)

    assert chat_json("system", "user") == ""


@pytest.mark.parametrize("error", [status_error(429), status_error(503), timeout_error()])
def test_one_failure_is_retried_after_2_seconds(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    fake = use_llm(monkeypatch, error, '{"ok": true}')

    assert chat_json("system", "user") == '{"ok": true}'

    assert len(fake.calls) == 2
    assert fake.sleeps == [2]


@pytest.mark.parametrize("error", [status_error(429), status_error(500), timeout_error()])
def test_two_failures_raise_unavailable(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    fake = use_llm(monkeypatch, error, error)

    with pytest.raises(LLMUnavailable):
        chat_json("system", "user")

    assert len(fake.calls) == 2


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, LLMAuthError), (403, LLMAuthError), (400, LLMRejected)],
)
def test_other_failures_are_not_retried(
    monkeypatch: pytest.MonkeyPatch, status: int, expected: type[LLMError]
) -> None:
    fake = use_llm(monkeypatch, status_error(status))

    with pytest.raises(expected):
        chat_json("system", "user")

    assert len(fake.calls) == 1
    assert fake.sleeps == []


def test_a_bad_key_after_a_retry_is_still_an_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    use_llm(monkeypatch, status_error(503), status_error(401))

    with pytest.raises(LLMAuthError):
        chat_json("system", "user")


def test_failures_never_log_the_key_or_the_email_text(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    use_llm(monkeypatch, status_error(429), status_error(500))

    with caplog.at_level(logging.DEBUG), pytest.raises(LLMUnavailable) as raised:
        chat_json("system", EMAIL_TEXT)

    written = caplog.text + str(raised.value)
    assert llm.logger.name in caplog.text  # the retry was logged
    assert get_settings().llm_api_key not in written
    assert EMAIL_TEXT not in written
    assert "provider said no" not in written  # the provider's own words are left out too
