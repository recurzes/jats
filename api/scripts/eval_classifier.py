"""Score the classifier on the fixture emails. Run from api/: python -m scripts.eval_classifier

Calls the real AI provider, once per email, with the LLM_* settings.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.classifier.llm import LLMError
from app.classifier.schema import Classification
from app.classifier.service import ClassificationFailed, classify
from app.gmail.parse import SNIPPET_LENGTH, ParsedEmail

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "classifier"
TARGET = 0.85

NOT_JOB_RELATED = "not job related"


@dataclass(frozen=True)
class Case:
    name: str
    email: ParsedEmail
    # A status, or NOT_JOB_RELATED.
    expected: str


def load_cases(folder: Path = FIXTURES) -> list[Case]:
    """Every email in the folder's JSON files, including the gitignored `local/` ones."""
    cases = []
    for path in sorted(folder.rglob("*.json")):
        for index, item in enumerate(json.loads(path.read_text(encoding="utf-8"))):
            address = item["from"].lower()
            name = item.get("name") or f"{path.stem}[{index}]"
            email = ParsedEmail(
                gmail_message_id=name,
                thread_id=name,
                from_address=address,
                from_domain=address.rpartition("@")[2],
                subject=item["subject"],
                snippet=item["body"][:SNIPPET_LENGTH],
                received_at=datetime.fromisoformat(item["date"]),
                body=item["body"],
            )
            cases.append(Case(name, email, item["expected"] or NOT_JOB_RELATED))
    return cases


def _answer(result: Classification | ClassificationFailed) -> str:
    if isinstance(result, ClassificationFailed):
        return f"failed ({result.reason})"
    if not result.is_job_related:
        return NOT_JOB_RELATED
    return str(result.status)


def evaluate(
    cases: list[Case],
    classify: Callable[[ParsedEmail], Classification | ClassificationFailed] = classify,
) -> float:
    """Classify every case, print the accuracy and each miss, and return the accuracy."""
    misses = []
    for case in cases:
        answer = _answer(classify(case.email))
        if answer != case.expected:
            misses.append((case, answer))

    correct = len(cases) - len(misses)
    accuracy = correct / len(cases)
    print(f"Accuracy: {correct}/{len(cases)} ({accuracy:.0%}), target {TARGET:.0%}")
    for case, answer in misses:
        print(f"MISS {case.name}: expected {case.expected}, got {answer}")
        print(f"     {case.email.subject}")
    return accuracy


def main() -> None:
    cases = load_cases(FIXTURES)
    if not cases:
        raise SystemExit(f"No emails found in {FIXTURES}")
    try:
        evaluate(cases)
    except LLMError as exc:
        raise SystemExit(f"Stopped: {exc}") from None


if __name__ == "__main__":
    main()
