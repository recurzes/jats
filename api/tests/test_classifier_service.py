import logging
from datetime import UTC, datetime

import pytest
from gmail_fake import load_fixture
from llm_fake import answer, status_error, use_llm
from sqlalchemy.orm import Session

from app.classifier.llm import LLMAuthError, LLMUnavailable
from app.classifier.prompts import RETRY_PROMPT, SYSTEM_PROMPT
from app.classifier.schema import Classification, Status
from app.classifier.service import ClassificationFailed, classify, classify_and_store
from app.config import get_settings
from app.gmail.models import Email, GmailAccount
from app.gmail.parse import ParsedEmail, parse_message

MALFORMED = "Sure! Here is the classification: rejected"


@pytest.fixture
def parsed() -> ParsedEmail:
    return parse_message(load_fixture("plain"))


@pytest.fixture
def email(db: Session, parsed: ParsedEmail) -> Email:
    account = GmailAccount(
        user_id=get_settings().owner_user_id,
        email_address="me@example.com",
        refresh_token_enc="enc",
    )
    db.add(account)
    db.flush()
    email = Email(
        account_id=account.id,
        gmail_message_id=parsed.gmail_message_id,
        thread_id=parsed.thread_id,
        from_address=parsed.from_address,
        from_domain=parsed.from_domain,
        subject=parsed.subject,
        snippet=parsed.snippet,
        received_at=parsed.received_at,
        is_candidate=True,
    )
    db.add(email)
    db.commit()
    return email


# --- classify


def test_a_good_answer_is_returned(monkeypatch: pytest.MonkeyPatch, parsed: ParsedEmail) -> None:
    fake = use_llm(monkeypatch, answer())

    result = classify(parsed)

    assert isinstance(result, Classification)
    assert (result.company, result.role, result.status) == (
        "Acme Corp",
        "React Developer",
        Status.ACKNOWLEDGED,
    )
    (call,) = fake.calls
    assert call["messages"][0]["content"] == SYSTEM_PROMPT
    (message,) = fake.user_messages()
    assert message.startswith("<email>\nFrom: careers@acme.example\n")
    assert "Subject: We received your application\n" in message
    assert "Thank you for applying to the React Developer position at Acme Corp." in message
    assert message.endswith("</email>")


def test_a_malformed_answer_is_retried_once(
    monkeypatch: pytest.MonkeyPatch, parsed: ParsedEmail
) -> None:
    fake = use_llm(monkeypatch, MALFORMED, answer(status="rejected"))

    result = classify(parsed)

    assert isinstance(result, Classification)
    assert result.status is Status.REJECTED
    first, second = fake.user_messages()
    assert second == f"{first}\n\n{RETRY_PROMPT}"


def test_two_malformed_answers_give_up(
    monkeypatch: pytest.MonkeyPatch, parsed: ParsedEmail
) -> None:
    fake = use_llm(monkeypatch, MALFORMED, '{"is_job_related": true, "confidence": 2}')

    result = classify(parsed)

    assert result == ClassificationFailed("Invalid AI answer: confidence")
    assert len(fake.calls) == 2


def test_a_refused_request_gives_up_without_a_retry(
    monkeypatch: pytest.MonkeyPatch, parsed: ParsedEmail
) -> None:
    fake = use_llm(monkeypatch, status_error(400))

    result = classify(parsed)

    assert result == ClassificationFailed("The AI provider refused the request (400)")
    assert len(fake.calls) == 1


def test_an_outage_is_raised(monkeypatch: pytest.MonkeyPatch, parsed: ParsedEmail) -> None:
    use_llm(monkeypatch, status_error(503), status_error(503))

    with pytest.raises(LLMUnavailable):
        classify(parsed)


def test_a_failure_logs_the_message_id_but_not_the_email_or_the_answer(
    monkeypatch: pytest.MonkeyPatch, parsed: ParsedEmail, caplog: pytest.LogCaptureFixture
) -> None:
    use_llm(monkeypatch, MALFORMED, MALFORMED)

    with caplog.at_level(logging.DEBUG):
        classify(parsed)

    (record,) = caplog.records
    assert record.data["gmail_message_id"] == parsed.gmail_message_id
    written = caplog.text + str(record.data)
    assert MALFORMED not in written
    assert "Thank you for applying" not in written
    assert parsed.subject not in written


# --- classify_and_store


def test_the_classification_is_saved_on_the_email(
    db: Session, monkeypatch: pytest.MonkeyPatch, email: Email, parsed: ParsedEmail
) -> None:
    use_llm(monkeypatch, answer(confidence=0.72))
    before = datetime.now(UTC)

    result = classify_and_store(db, email, parsed)

    assert isinstance(result, Classification)
    db.expire_all()
    assert email.classification == {
        "is_job_related": True,
        "company": "Acme Corp",
        "role": "React Developer",
        "status": "acknowledged",
        "confidence": 0.72,
    }
    assert email.confidence == 0.72
    assert email.processed_at >= before
    assert email.classification_attempts == 0


def test_classifying_the_same_email_twice_skips_the_second_time(
    db: Session, monkeypatch: pytest.MonkeyPatch, email: Email, parsed: ParsedEmail
) -> None:
    fake = use_llm(monkeypatch, answer())

    classify_and_store(db, email, parsed)
    processed_at = email.processed_at

    assert classify_and_store(db, email, parsed) is None
    assert len(fake.calls) == 1
    assert email.processed_at == processed_at


def test_an_email_that_is_not_job_related_is_processed_too(
    db: Session, monkeypatch: pytest.MonkeyPatch, email: Email, parsed: ParsedEmail
) -> None:
    use_llm(monkeypatch, answer(is_job_related=False, company=None, role=None, status=None))

    classify_and_store(db, email, parsed)

    db.expire_all()
    assert email.classification["is_job_related"] is False
    assert email.processed_at is not None


def test_a_failure_counts_an_attempt_and_leaves_the_email_unprocessed(
    db: Session, monkeypatch: pytest.MonkeyPatch, email: Email, parsed: ParsedEmail
) -> None:
    use_llm(monkeypatch, MALFORMED, MALFORMED, MALFORMED, MALFORMED)

    first = classify_and_store(db, email, parsed)
    classify_and_store(db, email, parsed)

    assert isinstance(first, ClassificationFailed)
    db.expire_all()
    assert email.classification_attempts == 2
    assert email.processed_at is None
    assert email.classification is None
    assert email.confidence is None


def test_a_failed_email_can_be_classified_later(
    db: Session, monkeypatch: pytest.MonkeyPatch, email: Email, parsed: ParsedEmail
) -> None:
    use_llm(monkeypatch, MALFORMED, MALFORMED, answer())

    classify_and_store(db, email, parsed)
    result = classify_and_store(db, email, parsed)

    assert isinstance(result, Classification)
    db.expire_all()
    assert email.classification_attempts == 1
    assert email.processed_at is not None


@pytest.mark.parametrize(
    ("errors", "expected"),
    [
        ((status_error(503), status_error(503)), LLMUnavailable),
        ((status_error(401),), LLMAuthError),
    ],
)
def test_an_outage_counts_no_attempt(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    email: Email,
    parsed: ParsedEmail,
    errors: tuple[Exception, ...],
    expected: type[Exception],
) -> None:
    use_llm(monkeypatch, *errors)

    with pytest.raises(expected):
        classify_and_store(db, email, parsed)

    db.expire_all()
    assert email.classification_attempts == 0
    assert email.processed_at is None
