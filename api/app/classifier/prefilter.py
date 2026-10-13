import re

from app.classifier.rules import JOB_BOARD_DOMAINS, SUBJECT_KEYWORDS

# Matches at the start of a word, so "applications" counts and "composition" does not.
_KEYWORDS = re.compile(
    r"\b(?:" + "|".join(re.escape(keyword) for keyword in SUBJECT_KEYWORDS) + ")",
    re.IGNORECASE,
)


def is_candidate(from_domain: str, subject: str, in_known_thread: bool = False) -> bool:
    """Cheap rules that decide whether an email is worth an AI call.

    `in_known_thread` says the email's thread already has an application. Such an email always
    counts, which catches a recruiter replying from a personal address.
    """
    if in_known_thread:
        return True
    domain = from_domain.lower()
    if any(domain == board or domain.endswith("." + board) for board in JOB_BOARD_DOMAINS):
        return True
    return _KEYWORDS.search(subject) is not None
