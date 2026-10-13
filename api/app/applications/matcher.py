"""Which application an email belongs to: its Gmail thread first, then the company name."""

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.models import Application
from app.classifier.schema import Status
from app.gmail.models import Email

COMPANY_SUFFIXES = frozenset({"inc", "llc", "ltd", "corp", "co", "company", "limited"})

# Removed without leaving a gap, so "AT&T", "L'Oreal" and "A.C.M.E." each stay one word.
_JOINING_PUNCTUATION = str.maketrans("", "", "'’.&")


def normalize_company(name: str) -> str:
    """The key that company matching compares: "Acme Corp." and "ACME" both give "acme"."""
    # NFKD splits an accented letter into the letter and its accent, which is then dropped.
    text = unicodedata.normalize("NFKD", name.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.translate(_JOINING_PUNCTUATION)
    words = "".join(char if char.isalnum() else " " for char in text).split()
    # Never the last word: a company called "The Company" keeps a key.
    while len(words) > 1 and words[-1] in COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


def find_by_thread(db: Session, thread_id: str) -> Application | None:
    """The application of an earlier email in this Gmail thread."""
    return db.scalar(
        select(Application)
        .join(Email, Email.application_id == Application.id)
        .where(Email.thread_id == thread_id)
        .order_by(Email.received_at.desc())
        .limit(1)
    )


def find_by_company(db: Session, company_key: str) -> Application | None:
    """The most recently updated application for this company that is still open.

    None means the caller creates a new application. An empty key never matches, so emails with
    no company do not pile up on one application.
    """
    if not company_key:
        return None
    return db.scalar(
        select(Application)
        .where(Application.company_key == company_key, Application.status != Status.REJECTED)
        .order_by(Application.last_event_at.desc())
        .limit(1)
    )
