import json
from pathlib import Path

import pytest
from llm_fake import answer, status_error, use_llm

from app.classifier.schema import Classification, Status
from app.classifier.service import ClassificationFailed
from app.gmail.parse import ParsedEmail
from scripts import eval_classifier
from scripts.eval_classifier import NOT_JOB_RELATED, evaluate, load_cases

EXPECTED = {status.value for status in Status} | {NOT_JOB_RELATED}


def test_the_fixture_set_has_20_emails_covering_every_answer() -> None:
    # Only the committed file: `local/` holds whatever real emails this machine has.
    cases = [case for case in load_cases() if case.name in committed_names()]

    assert len(cases) == 20
    assert len({case.name for case in cases}) == 20
    assert {case.expected for case in cases} == EXPECTED
    assert all(case.email.body and case.email.from_domain for case in cases)


def committed_names() -> set[str]:
    path = eval_classifier.FIXTURES / "synthetic.json"
    return {item["name"] for item in json.loads(path.read_text(encoding="utf-8"))}


def write_cases(folder: Path, *expected: str | None) -> None:
    items = [
        {
            "name": f"case-{index}",
            "from": "Careers@Acme.example",
            "subject": f"Subject {index}",
            "date": "2026-10-13T08:00:00+00:00",
            "body": "Thank you for applying.",
            "expected": status,
        }
        for index, status in enumerate(expected)
    ]
    (folder / "local").mkdir()
    (folder / "local" / "emails.json").write_text(json.dumps(items), encoding="utf-8")


def test_load_cases_reads_subfolders(tmp_path: Path) -> None:
    write_cases(tmp_path, "rejected", None)

    first, second = load_cases(tmp_path)

    assert (first.name, first.expected) == ("case-0", "rejected")
    assert second.expected == NOT_JOB_RELATED
    assert first.email.from_address == "careers@acme.example"
    assert first.email.from_domain == "acme.example"
    assert first.email.received_at.isoformat() == "2026-10-13T08:00:00+00:00"


def test_evaluate_prints_the_accuracy_and_each_miss(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_cases(tmp_path, "acknowledged", "rejected", None, "update")
    answers = {
        "case-0": Classification.model_validate_json(answer()),
        "case-1": Classification.model_validate_json(answer(status="update")),
        "case-2": Classification.model_validate_json(answer(is_job_related=False)),
        "case-3": ClassificationFailed("Invalid AI answer: status"),
    }

    def fake_classify(email: ParsedEmail) -> Classification | ClassificationFailed:
        return answers[email.gmail_message_id]

    accuracy = evaluate(load_cases(tmp_path), fake_classify)

    assert accuracy == 0.5
    assert capsys.readouterr().out.splitlines() == [
        "Accuracy: 2/4 (50%), target 85%",
        "MISS case-1: expected rejected, got update",
        "     Subject 1",
        "MISS case-3: expected update, got failed (Invalid AI answer: status)",
        "     Subject 3",
    ]


def test_main_runs_the_cases_through_the_classifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_cases(tmp_path, "acknowledged", None)
    monkeypatch.setattr(eval_classifier, "FIXTURES", tmp_path)
    use_llm(monkeypatch, answer(), answer(is_job_related=False, status=None))

    eval_classifier.main()

    assert capsys.readouterr().out.strip() == "Accuracy: 2/2 (100%), target 85%"


def test_main_stops_with_a_message_when_the_provider_is_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_cases(tmp_path, "acknowledged")
    monkeypatch.setattr(eval_classifier, "FIXTURES", tmp_path)
    use_llm(monkeypatch, status_error(401))

    with pytest.raises(SystemExit, match="refused the API key"):
        eval_classifier.main()
