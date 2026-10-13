import pytest
from llm_fake import answer
from pydantic import ValidationError

from app.classifier.schema import Classification, Status


def test_statuses_are_the_four_of_v1() -> None:
    assert [status.value for status in Status] == ["acknowledged", "replied", "update", "rejected"]


def test_valid_json_becomes_a_classification() -> None:
    result = Classification.model_validate_json(answer(status="rejected", confidence=0.8))

    assert result.is_job_related is True
    assert result.company == "Acme Corp"
    assert result.role == "React Developer"
    assert result.status is Status.REJECTED
    assert result.confidence == 0.8


def test_an_email_that_is_not_job_related_needs_no_status() -> None:
    result = Classification.model_validate_json(
        '{"is_job_related": false, "company": null, "role": null, "status": null, "confidence": 1}'
    )

    assert result.is_job_related is False
    assert result.status is None


def test_blank_text_is_missing_and_the_status_may_be_capitalised() -> None:
    result = Classification.model_validate_json(answer(company=" ", role="", status="Update"))

    assert result.company is None
    assert result.role is None
    assert result.status is Status.UPDATE


def test_dumps_to_plain_json_values() -> None:
    result = Classification.model_validate_json(answer())

    assert result.model_dump(mode="json") == {
        "is_job_related": True,
        "company": "Acme Corp",
        "role": "React Developer",
        "status": "acknowledged",
        "confidence": 0.93,
    }


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Sure! Here is the JSON you asked for.",
        '{"is_job_related": true',  # cut off
        "[]",
        '{"company": "Acme Corp", "status": "rejected", "confidence": 0.9}',  # no is_job_related
        answer(status=None),  # job related, so the status is required
        answer(status=""),
        answer(status="offer"),  # not a V1 status
        answer(confidence=1.5),
        answer(confidence=-0.1),
        answer(confidence=None),
    ],
)
def test_invalid_json_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        Classification.model_validate_json(text)
