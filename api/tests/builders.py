"""Rows the application tests start from."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.applications.matcher import normalize_company
from app.applications.models import Application
from app.config import get_settings
from app.gmail.models import Email, GmailAccount

RECEIVED_AT = datetime(2026, 10, 13, 8, 0, tzinfo=UTC)


def add_account(db: Session) -> GmailAccount:
    account = GmailAccount(
        user_id=get_settings().owner_user_id,
        email_address="me@example.com",
        refresh_token_enc="enc",
    )
    db.add(account)
    db.commit()
    return account


def add_email(db: Session, account: GmailAccount, message_id: str, **fields: Any) -> Email:
    """A candidate email in a thread of its own; keyword arguments override columns."""
    values = {
        "account_id": account.id,
        "gmail_message_id": message_id,
        "thread_id": f"thread-{message_id}",
        "from_address": "careers@acme.example",
        "from_domain": "acme.example",
        "subject": "We received your application",
        "snippet": "Thank you for applying",
        "received_at": RECEIVED_AT,
        "is_candidate": True,
    }
    email = Email(**(values | fields))
    db.add(email)
    db.commit()
    return email


def add_application(db: Session, company: str = "Acme Corp", **fields: Any) -> Application:
    values = {
        "user_id": get_settings().owner_user_id,
        "company": company,
        "company_key": normalize_company(company),
        "status": "acknowledged",
        "last_event_at": RECEIVED_AT,
    }
    application = Application(**(values | fields))
    db.add(application)
    db.commit()
    return application


def later(minutes: int) -> datetime:
    return RECEIVED_AT + timedelta(minutes=minutes)
