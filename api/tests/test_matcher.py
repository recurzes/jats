import pytest
from builders import add_account, add_application, add_email, later
from sqlalchemy.orm import Session

from app.applications.matcher import find_by_company, find_by_thread, normalize_company

# --- normalize_company


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Acme Corp.", "acme"),
        ("acme", "acme"),
        ("ACME", "acme"),
        ("  Acme   Corp  ", "acme"),
        ("Acme, Inc.", "acme"),
        ("Acme LLC", "acme"),
        ("Acme Co., Ltd.", "acme"),
        ("Acme Company Limited", "acme"),
        ("Globex-Initech (Remote)", "globex initech remote"),
        ("AT&T", "att"),
        ("Johnson & Johnson", "johnson johnson"),
        ("L'Oréal", "loreal"),
        ("Société Générale", "societe generale"),
        ("Straße GmbH", "strasse gmbh"),
        ("ＡＣＭＥ　Ｃｏｒｐ", "acme"),  # full-width letters and space
        ("株式会社トヨタ", "株式会社トヨタ"),
        ("Corp Solutions", "corp solutions"),  # only a trailing suffix is dropped
        ("The Company", "the"),
        ("Company", "company"),  # never dropped down to nothing
        ("", ""),
        ("   ", ""),
        ("...", ""),
    ],
)
def test_normalize_company(name: str, key: str) -> None:
    assert normalize_company(name) == key


def test_normalizing_a_key_again_changes_nothing() -> None:
    key = normalize_company("Société Générale Co., Ltd.")

    assert normalize_company(key) == key


# --- find_by_thread


def test_find_by_thread_returns_the_application_of_an_earlier_email(db: Session) -> None:
    account = add_account(db)
    application = add_application(db)
    add_application(db, "Globex")
    add_email(db, account, "a", thread_id="t1", application_id=application.id)

    assert find_by_thread(db, "t1").id == application.id


def test_find_by_thread_ignores_other_threads_and_unmatched_emails(db: Session) -> None:
    account = add_account(db)
    application = add_application(db)
    add_email(db, account, "a", thread_id="t1", application_id=application.id)
    add_email(db, account, "b", thread_id="t2")

    assert find_by_thread(db, "t2") is None
    assert find_by_thread(db, "t3") is None


def test_find_by_thread_follows_the_newest_matched_email(db: Session) -> None:
    account = add_account(db)
    old, new = add_application(db), add_application(db, "Globex")
    add_email(db, account, "a", thread_id="t1", application_id=old.id)
    add_email(db, account, "b", thread_id="t1", application_id=new.id, received_at=later(5))
    add_email(db, account, "c", thread_id="t1", received_at=later(9))

    assert find_by_thread(db, "t1").id == new.id


# --- find_by_company


def test_find_by_company_picks_the_newest_open_application(db: Session) -> None:
    add_application(db, last_event_at=later(1))
    newest_open = add_application(db, "ACME Inc.", status="replied", last_event_at=later(2))
    add_application(db, status="rejected", last_event_at=later(3))
    add_application(db, "Globex", last_event_at=later(4))

    assert find_by_company(db, "acme").id == newest_open.id


def test_find_by_company_finds_nothing_when_every_application_is_rejected(db: Session) -> None:
    add_application(db, status="rejected")

    assert find_by_company(db, "acme") is None
    assert find_by_company(db, "globex") is None


def test_an_empty_key_never_matches(db: Session) -> None:
    add_application(db, "Unknown", company_key="")

    assert find_by_company(db, "") is None
