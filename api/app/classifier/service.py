"""Email in, classification out: the AI call, its validation, and what is saved on the email."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.classifier.llm import LLMRejected, chat_json
from app.classifier.prompts import RETRY_PROMPT, SYSTEM_PROMPT, build_user_message
from app.classifier.schema import Classification
from app.gmail.models import Email
from app.gmail.parse import ParsedEmail

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationFailed:
    """The AI gave no usable answer for this email, even after the retry."""

    reason: str


def _invalid_fields(exc: ValidationError) -> str:
    """Which fields were wrong. Not `str(exc)`: that quotes the AI's answer."""
    fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
    return ", ".join(field for field in fields if field) or "not a JSON object"


def classify(parsed: ParsedEmail) -> Classification | ClassificationFailed:
    """Ask the AI about one email. Bad output is retried once, then given up on.

    `LLMUnavailable` and `LLMAuthError` are raised: they say the provider is down or the key is
    wrong, not that anything is wrong with this email.
    """
    user = build_user_message(parsed.from_address, parsed.subject, parsed.received_at, parsed.body)
    reason = ""
    for message in (user, f"{user}\n\n{RETRY_PROMPT}"):
        try:
            return Classification.model_validate_json(chat_json(SYSTEM_PROMPT, message))
        except ValidationError as exc:
            reason = f"Invalid AI answer: {_invalid_fields(exc)}"
        except LLMRejected as exc:
            reason = str(exc)
            break
    logger.warning(
        "Classification failed",
        extra={"data": {"gmail_message_id": parsed.gmail_message_id, "reason": reason}},
    )
    return ClassificationFailed(reason)


def classify_and_store(
    db: Session, email: Email, parsed: ParsedEmail
) -> Classification | ClassificationFailed | None:
    """Classify the email and save the result on its row. None when it was already processed.

    A failure counts one attempt and leaves `processed_at` empty, so the email can be tried
    again. A provider outage is raised and counts nothing.
    """
    if email.processed_at is not None:
        return None

    result = classify(parsed)
    if isinstance(result, ClassificationFailed):
        email.classification_attempts += 1
    else:
        email.classification = result.model_dump(mode="json")
        email.confidence = result.confidence
        email.processed_at = datetime.now(UTC)
    db.commit()
    return result
