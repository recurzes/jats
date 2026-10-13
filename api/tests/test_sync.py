import logging
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from gmail_fake import FakeGmail, added, http_error, load_fixture, message
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.oauth_state import make_state
from app.config import get_settings
from app.gmail import oauth, sync
from app.gmail.client import GmailAuthError
from app.gmail.models import (
    AccountState,
    Email,
    GmailAccount,
    SyncResult,
    SyncRun,
    SyncTrigger,
)
from app.gmail.sync import run_sync, sync_lock, sync_owner_account

FIXTURES = ("plain", "multipart", "html_only")


@pytest.fixture
def account(db: Session) -> GmailAccount:
    account = GmailAccount(
        user_id=get_settings().owner_user_id,
        email_address="me@example.com",
        refresh_token_enc="enc",
    )
    db.add(account)
    db.commit()
    return account


@pytest.fixture
def use_gmail(monkeypatch: pytest.MonkeyPatch):
    """Make the sync talk to this fake instead of building a real Gmail service."""

    def use(gmail: FakeGmail) -> FakeGmail:
        monkeypatch.setattr(sync, "get_gmail_service", lambda account: gmail)
        return gmail

    return use


@pytest.fixture
def own_session(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give sync_owner_account the test's session instead of a new one."""
    monkeypatch.setattr(sync, "SessionLocal", lambda: nullcontext(db))


def emails(db: Session) -> list[Email]:
    return list(db.scalars(select(Email).order_by(Email.received_at)))


def runs(db: Session) -> list[SyncRun]:
    return list(db.scalars(select(SyncRun).order_by(SyncRun.started_at)))


# --- run_sync: what gets stored


def test_first_sync_stores_the_last_7_days(db: Session, account: GmailAccount, use_gmail) -> None:
    gmail = use_gmail(
        FakeGmail(
            messages=[load_fixture(name) for name in FIXTURES],
            profile={"emailAddress": "me@example.com", "historyId": "777"},
        )
    )

    run = run_sync(db, account, SyncTrigger.MANUAL)

    assert run.result == SyncResult.OK
    assert (run.emails_seen, run.emails_new, run.emails_classified) == (3, 3, 0)
    plain, multipart, html_only = emails(db)
    assert plain.account_id == account.id
    assert plain.gmail_message_id == "18f0a1b2c3d4e5f6"
    assert plain.thread_id == "18f0a1b2c3d4e5f6"
    assert plain.from_address == "careers@acme.example"
    assert plain.from_domain == "acme.example"
    assert plain.subject == "We received your application"
    assert plain.snippet.startswith("Hi Lance, Thank you for applying")
    assert plain.received_at.isoformat() == "2026-10-13T08:00:00+00:00"
    assert plain.classification is None
    assert plain.classification_attempts == 0
    assert plain.processed_at is None
    assert [email.is_candidate for email in (plain, multipart, html_only)] == [True, True, True]
    assert multipart.thread_id == "18f0a9998887776f"
    assert html_only.from_domain == "indeed.com"
    # The 7-day listing was used, and the history id was read before it.
    assert [name for name, _ in gmail.calls[:2]] == ["getProfile", "messages.list"]
    assert gmail.called("history.list") == []
    assert account.history_id == "777"


def test_sync_stores_messages_oldest_first(db: Session, account: GmailAccount, use_gmail) -> None:
    gmail = use_gmail(FakeGmail(messages=[message("old"), message("new")]))

    run_sync(db, account, SyncTrigger.MANUAL)

    # Gmail lists the newest first.
    assert gmail.called("messages.list")
    assert [call["id"] for call in gmail.called("messages.get")] == ["old", "new"]


def test_the_body_is_never_stored(db: Session, account: GmailAccount, use_gmail) -> None:
    use_gmail(FakeGmail(messages=[load_fixture("plain")]))

    run_sync(db, account, SyncTrigger.MANUAL)

    email = emails(db)[0]
    stored = [str(getattr(email, column.name)) for column in Email.__table__.columns]
    assert not any("hiring team" in value for value in stored)
    assert all(len(value) <= 500 for value in stored)


def test_emails_that_fail_the_prefilter_are_stored_as_not_candidates(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    newsletter = load_fixture("plain")
    newsletter["payload"]["headers"] = [
        {"name": "From", "value": "News <news@shop.example>"},
        {"name": "Subject", "value": "This week's deals"},
    ]
    use_gmail(FakeGmail(messages=[newsletter]))

    run_sync(db, account, SyncTrigger.MANUAL)

    assert [email.is_candidate for email in emails(db)] == [False]


def test_a_second_sync_adds_no_duplicates(db: Session, account: GmailAccount, use_gmail) -> None:
    gmail = use_gmail(
        FakeGmail(
            messages=[message("a"), message("b"), message("c")],
            profile={"emailAddress": "me@example.com", "historyId": "777"},
            # Gmail reports the same messages again.
            history_pages=[{"history": [added("a", "b", "c")], "historyId": "800"}],
        )
    )
    run_sync(db, account, SyncTrigger.MANUAL)
    gmail.calls.clear()

    run = run_sync(db, account, SyncTrigger.MANUAL)

    assert run.result == SyncResult.OK
    assert (run.emails_seen, run.emails_new) == (3, 0)
    assert len(emails(db)) == 3
    # Stored ids are not fetched again.
    assert gmail.called("messages.get") == []
    assert gmail.called("history.list")[0]["startHistoryId"] == "777"
    assert account.history_id == "800"


def test_incremental_sync_stores_only_the_new_messages(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    account.history_id = "500"
    db.commit()
    gmail = use_gmail(
        FakeGmail(
            messages=[message("a"), message("b")],
            history_pages=[{"history": [added("b")], "historyId": "560"}],
        )
    )

    run = run_sync(db, account, SyncTrigger.SCHEDULE)

    assert run.result == SyncResult.OK
    assert run.trigger == SyncTrigger.SCHEDULE
    assert (run.emails_seen, run.emails_new) == (1, 1)
    assert [email.gmail_message_id for email in emails(db)] == ["b"]
    # No inbox listing, and no extra profile call: history.list gave the new history id.
    assert gmail.called("messages.list") == []
    assert gmail.called("getProfile") == []
    assert account.history_id == "560"


def test_a_message_deleted_before_it_is_fetched_is_skipped(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    account.history_id = "500"
    db.commit()
    use_gmail(
        FakeGmail(
            messages=[message("a")],
            history_pages=[{"history": [added("gone", "a")], "historyId": "560"}],
        )
    )

    run = run_sync(db, account, SyncTrigger.MANUAL)

    assert run.result == SyncResult.OK
    assert (run.emails_seen, run.emails_new) == (2, 1)
    assert account.history_id == "560"


# --- run_sync: expired history id


def test_an_expired_history_id_falls_back_to_the_7_day_listing(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    account.history_id = "1"
    db.commit()
    gmail = use_gmail(
        FakeGmail(
            messages=[message("a"), message("b")],
            history_pages=[http_error(404)],
            profile={"emailAddress": "me@example.com", "historyId": "900"},
        )
    )

    run = run_sync(db, account, SyncTrigger.SCHEDULE)

    assert run.result == SyncResult.FALLBACK_FULL
    assert run.error is None
    assert (run.emails_seen, run.emails_new) == (2, 2)
    assert [name for name, _ in gmail.calls[:3]] == ["history.list", "getProfile", "messages.list"]
    assert gmail.called("messages.list")[0]["q"] == "newer_than:7d"
    assert account.history_id == "900"


def test_the_fallback_does_not_duplicate_stored_messages(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    gmail = use_gmail(FakeGmail(messages=[message("a")]))
    run_sync(db, account, SyncTrigger.MANUAL)
    gmail.stored["b"] = message("b")
    gmail.history_pages = [http_error(404)]

    run = run_sync(db, account, SyncTrigger.MANUAL)

    assert run.result == SyncResult.FALLBACK_FULL
    assert (run.emails_seen, run.emails_new) == (2, 1)
    assert len(emails(db)) == 2


# --- run_sync: sync_runs rows and logging


def test_a_failing_sync_still_leaves_an_error_row(
    db: Session, account: GmailAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(account: GmailAccount) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(sync, "get_gmail_service", explode)

    run = run_sync(db, account, SyncTrigger.SCHEDULE)

    saved = runs(db)
    assert [saved_run.id for saved_run in saved] == [run.id]
    assert saved[0].result == SyncResult.ERROR
    assert saved[0].error == "boom"
    assert saved[0].trigger == SyncTrigger.SCHEDULE
    assert saved[0].finished_at is not None
    assert saved[0].finished_at >= saved[0].started_at
    # Only a Gmail auth failure asks for a reconnect.
    assert account.state == AccountState.OK


def test_a_failure_part_way_keeps_stored_rows_but_not_the_history_id(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    account.history_id = "500"
    db.commit()
    gmail = use_gmail(
        FakeGmail(
            messages=[message("a"), message("c")],
            history_pages=[{"history": [added("a", "b", "c")], "historyId": "560"}],
        )
    )
    gmail.stored["b"] = http_error(503)

    run = run_sync(db, account, SyncTrigger.SCHEDULE)

    assert run.result == SyncResult.ERROR
    assert run.error == "Gmail server error (503)"
    assert (run.emails_seen, run.emails_new) == (3, 1)
    assert [email.gmail_message_id for email in emails(db)] == ["a"]
    # Not advanced, so the next run reads "b" and "c" again.
    assert account.history_id == "500"

    gmail.stored["b"] = message("b")
    retry = run_sync(db, account, SyncTrigger.SCHEDULE)

    assert (retry.result, retry.emails_new) == (SyncResult.OK, 2)
    assert len(emails(db)) == 3
    assert account.history_id == "560"


def test_each_run_logs_one_summary_line(
    db: Session, account: GmailAccount, use_gmail, caplog: pytest.LogCaptureFixture
) -> None:
    use_gmail(FakeGmail(messages=[message("a")]))

    with caplog.at_level(logging.INFO, logger="app.gmail.sync"):
        run = run_sync(db, account, SyncTrigger.MANUAL)

    summaries = [record for record in caplog.records if hasattr(record, "data")]
    assert len(summaries) == 1
    data = summaries[0].data
    assert data["sync_run_id"] == str(run.id)
    assert data["trigger"] == "manual"
    assert data["result"] == "ok"
    assert (data["emails_seen"], data["emails_new"], data["emails_classified"]) == (1, 1, 0)
    assert data["duration_ms"] >= 0


# --- run_sync: one at a time


def test_a_sync_that_overlaps_a_running_one_is_skipped(
    db: Session, account: GmailAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = FakeGmail(messages=[message("a")])
    overlapping: list[SyncRun] = []

    def get_gmail_service(account: GmailAccount) -> FakeGmail:
        # Called while the first sync holds the lock: start a second one right here.
        if not overlapping:
            overlapping.append(run_sync(db, account, SyncTrigger.MANUAL))
        return gmail

    monkeypatch.setattr(sync, "get_gmail_service", get_gmail_service)

    first = run_sync(db, account, SyncTrigger.SCHEDULE)

    second = overlapping[0]
    assert (first.result, first.emails_new) == (SyncResult.OK, 1)
    assert second.result == SyncResult.SKIPPED_LOCKED
    assert second.finished_at is not None
    assert (second.emails_seen, second.emails_new) == (0, 0)
    assert len(runs(db)) == 2
    # Only the first one talked to Gmail.
    assert len(gmail.called("messages.list")) == 1


def test_the_lock_is_free_again_after_a_sync(
    db: Session, account: GmailAccount, use_gmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gmail(FakeGmail())
    assert run_sync(db, account, SyncTrigger.MANUAL).result == SyncResult.OK

    def explode(account: GmailAccount) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(sync, "get_gmail_service", explode)
    assert run_sync(db, account, SyncTrigger.MANUAL).result == SyncResult.ERROR

    with sync_lock() as locked:
        assert locked


def test_sync_lock_is_held_by_one_connection_at_a_time() -> None:
    with sync_lock() as first:
        with sync_lock() as second:
            assert (first, second) == (True, False)
        # Leaving the block that did not get the lock must not release it.
        with sync_lock() as third:
            assert not third


# --- Gmail access lost


def test_invalid_grant_marks_the_account_needs_reauth(
    db: Session, account: GmailAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(account: GmailAccount) -> None:
        raise GmailAuthError("Gmail refused the stored refresh token (invalid_grant)")

    monkeypatch.setattr(sync, "get_gmail_service", refuse)

    run = run_sync(db, account, SyncTrigger.SCHEDULE)

    assert run.result == SyncResult.ERROR
    assert run.error == "Gmail refused the stored refresh token (invalid_grant)"
    db.refresh(account)
    assert account.state == AccountState.NEEDS_REAUTH
    assert account.last_error == "Gmail refused the stored refresh token (invalid_grant)"


def test_losing_access_mid_sync_keeps_existing_data(
    db: Session, account: GmailAccount, use_gmail
) -> None:
    gmail = use_gmail(FakeGmail(messages=[message("a"), message("b")]))
    gmail.stored["b"] = http_error(401)

    run_sync(db, account, SyncTrigger.SCHEDULE)

    assert account.state == AccountState.NEEDS_REAUTH
    assert [email.gmail_message_id for email in emails(db)] == ["a"]
    assert account.history_id is None


def test_the_scheduler_skips_an_account_that_needs_reauth_until_it_is_reconnected(
    client: TestClient,
    db: Session,
    account: GmailAccount,
    own_session: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(account: GmailAccount) -> None:
        raise GmailAuthError("Gmail refused the stored refresh token (invalid_grant)")

    monkeypatch.setattr(sync, "get_gmail_service", refuse)
    sync_owner_account(SyncTrigger.SCHEDULE)
    assert account.state == AccountState.NEEDS_REAUTH
    assert len(runs(db)) == 1

    # The next scheduled run does not touch Gmail or add a row.
    def unexpected(account: GmailAccount) -> None:
        raise AssertionError("a needs_reauth account must not be synced")

    monkeypatch.setattr(sync, "get_gmail_service", unexpected)
    sync_owner_account(SyncTrigger.SCHEDULE)
    assert len(runs(db)) == 1

    # Completing the connect flow again makes it syncable.
    monkeypatch.setattr(oauth, "exchange_code", lambda code: ("new-token", "me@example.com"))
    state = make_state(get_settings().owner_user_id)
    client.get("/auth/google/callback", params={"code": "c", "state": state})
    db.refresh(account)
    assert account.state == AccountState.OK
    assert account.last_error is None

    monkeypatch.setattr(sync, "get_gmail_service", lambda account: FakeGmail())
    sync_owner_account(SyncTrigger.SCHEDULE)
    assert [run.result for run in runs(db)] == [SyncResult.ERROR, SyncResult.OK]


# --- sync_owner_account


def test_sync_owner_account_does_nothing_without_an_account(db: Session, own_session: None) -> None:
    sync_owner_account(SyncTrigger.SCHEDULE)

    assert db.scalar(select(func.count()).select_from(SyncRun)) == 0


def test_sync_owner_account_records_the_trigger(
    db: Session, account: GmailAccount, own_session: None, use_gmail
) -> None:
    use_gmail(FakeGmail(messages=[message("a")]))

    sync_owner_account(SyncTrigger.SCHEDULE)

    assert [(run.trigger, run.result, run.emails_new) for run in runs(db)] == [
        (SyncTrigger.SCHEDULE, SyncResult.OK, 1)
    ]
