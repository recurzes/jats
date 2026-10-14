import uuid
from collections.abc import Callable
from datetime import datetime

import pytest
from builders import RECEIVED_AT, add_account, add_application, add_email, later
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.models import Application, EventSource, StatusEvent
from app.printing.models import Device, JobState, PrintJob

Headers = dict[str, str]


def add_event(db: Session, application: Application, **fields: object) -> StatusEvent:
    values = {
        "application_id": application.id,
        "to_status": application.status,
        "source": EventSource.AI,
        "created_at": RECEIVED_AT,
    }
    event = StatusEvent(**(values | fields))
    db.add(event)
    db.commit()
    return event


def companies(response) -> list[str]:  # noqa: ANN001
    assert response.status_code == 200
    return [application["company"] for application in response.json()]


# --- GET /applications


def test_list_returns_the_card_fields(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    account = add_account(db)
    application = add_application(db, role="Backend Developer", needs_review=True)
    add_email(db, account, "old", application_id=application.id, subject="We got it")
    add_email(
        db,
        account,
        "new",
        application_id=application.id,
        subject="An update",
        received_at=later(30),
    )

    response = client.get("/applications", headers=auth_headers)

    assert response.status_code == 200
    (card,) = response.json()
    assert set(card) == {
        "id",
        "company",
        "role",
        "status",
        "needs_review",
        "last_event_at",
        "last_email_subject",
        "last_email_at",
    }
    assert card["id"] == str(application.id)
    assert card["company"] == "Acme Corp"
    assert card["role"] == "Backend Developer"
    assert card["status"] == "acknowledged"
    assert card["needs_review"] is True
    assert datetime.fromisoformat(card["last_event_at"]) == RECEIVED_AT
    assert card["last_email_subject"] == "An update"
    assert datetime.fromisoformat(card["last_email_at"]) == later(30)


def test_list_includes_an_application_without_emails(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    add_application(db)

    (card,) = client.get("/applications", headers=auth_headers).json()

    assert card["last_email_subject"] is None
    assert card["last_email_at"] is None


def test_list_is_sorted_by_last_event_newest_first(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    add_application(db, "Middle", last_event_at=later(10))
    add_application(db, "Oldest", last_event_at=later(0))
    add_application(db, "Newest", last_event_at=later(20))

    response = client.get("/applications", headers=auth_headers)

    assert companies(response) == ["Newest", "Middle", "Oldest"]


def test_list_filters_by_status(client: TestClient, db: Session, auth_headers: Headers) -> None:
    add_application(db, "Acme", status="acknowledged")
    add_application(db, "Globex", status="rejected")

    response = client.get("/applications", params={"status": "rejected"}, headers=auth_headers)

    assert companies(response) == ["Globex"]


def test_list_filters_by_needs_review(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    add_application(db, "Acme", needs_review=True)
    add_application(db, "Globex", needs_review=False)

    flagged = client.get("/applications", params={"needs_review": "true"}, headers=auth_headers)
    clear = client.get("/applications", params={"needs_review": "false"}, headers=auth_headers)

    assert companies(flagged) == ["Acme"]
    assert companies(clear) == ["Globex"]


def test_list_combines_both_filters(client: TestClient, db: Session, auth_headers: Headers) -> None:
    add_application(db, "Acme", status="rejected", needs_review=True)
    add_application(db, "Globex", status="rejected")
    add_application(db, "Initech", status="replied", needs_review=True)

    response = client.get(
        "/applications", params={"status": "rejected", "needs_review": "true"}, headers=auth_headers
    )

    assert companies(response) == ["Acme"]


def test_list_treats_empty_filters_as_no_filter(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    add_application(db, "Acme", status="rejected", needs_review=True)
    add_application(db, "Globex", last_event_at=later(-10))

    response = client.get("/applications?status=&needs_review=", headers=auth_headers)

    assert companies(response) == ["Acme", "Globex"]


def test_list_rejects_an_unknown_status(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/applications", params={"status": "hired"}, headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


def test_list_leaves_out_other_users_applications(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    add_application(db, user_id=uuid.uuid4())

    assert client.get("/applications", headers=auth_headers).json() == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/applications"),
        ("GET", "/applications/{id}"),
        ("PATCH", "/applications/{id}"),
        ("POST", "/applications/{id}/reprint"),
    ],
)
def test_the_board_is_owner_only(
    client: TestClient, db: Session, make_token: Callable[..., str], method: str, path: str
) -> None:
    url = path.format(id=add_application(db).id)
    stranger = {"Authorization": f"Bearer {make_token(sub=uuid.uuid4())}"}

    no_token = client.request(method, url, json={})
    not_owner = client.request(method, url, json={}, headers=stranger)

    assert no_token.status_code == 401
    assert no_token.json()["error"]["code"] == "AUTH_INVALID"
    assert not_owner.status_code == 403
    assert not_owner.json()["error"]["code"] == "NOT_OWNER"
    assert db.scalars(select(PrintJob)).all() == []


# --- GET /applications/{id}


def test_detail_has_the_emails_and_the_status_events(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    account = add_account(db)
    application = add_application(db, role="Backend Developer", status="rejected")
    first = add_email(db, account, "first", application_id=application.id)
    second = add_email(
        db,
        account,
        "second",
        application_id=application.id,
        subject="Your application",
        from_address="hr@acme.example",
        snippet="Unfortunately",
        received_at=later(60),
    )
    add_email(db, account, "elsewhere")
    created = add_event(db, application, to_status="acknowledged", email_id=first.id)
    rejected = add_event(
        db,
        application,
        from_status="acknowledged",
        to_status="rejected",
        email_id=second.id,
        created_at=later(60),
    )

    response = client.get(f"/applications/{application.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(application.id)
    assert body["company"] == "Acme Corp"
    assert body["role"] == "Backend Developer"
    assert body["status"] == "rejected"
    assert body["last_email_subject"] == "Your application"
    assert [email["id"] for email in body["emails"]] == [str(second.id), str(first.id)]
    assert body["emails"][0] == {
        "id": str(second.id),
        "subject": "Your application",
        "from_address": "hr@acme.example",
        "snippet": "Unfortunately",
        "received_at": body["emails"][0]["received_at"],
    }
    assert datetime.fromisoformat(body["emails"][0]["received_at"]) == later(60)
    assert [event["id"] for event in body["status_events"]] == [str(rejected.id), str(created.id)]
    newest, oldest = body["status_events"]
    assert (newest["from_status"], newest["to_status"]) == ("acknowledged", "rejected")
    assert newest["source"] == "ai"
    assert newest["email_id"] == str(second.id)
    assert oldest["from_status"] is None


def test_detail_of_an_unknown_id_is_404(client: TestClient, auth_headers: Headers) -> None:
    response = client.get(f"/applications/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_detail_of_another_users_application_is_404(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db, user_id=uuid.uuid4())

    response = client.get(f"/applications/{application.id}", headers=auth_headers)

    assert response.status_code == 404


def test_detail_of_a_malformed_id_is_422(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/applications/not-a-uuid", headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


# --- PATCH /applications/{id}


def test_patch_status_records_a_manual_event_and_prints_nothing(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db)

    response = client.patch(
        f"/applications/{application.id}", json={"status": "rejected"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    db.refresh(application)
    assert application.status == "rejected"
    assert application.last_event_at > RECEIVED_AT
    event = db.scalars(select(StatusEvent)).one()
    assert event.application_id == application.id
    assert (event.from_status, event.to_status) == ("acknowledged", "rejected")
    assert event.source == EventSource.MANUAL
    assert event.email_id is None
    assert [item["id"] for item in body["status_events"]] == [str(event.id)]
    assert db.scalars(select(PrintJob)).all() == []


def test_patch_status_clears_needs_review(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db, needs_review=True)

    response = client.patch(
        f"/applications/{application.id}", json={"status": "replied"}, headers=auth_headers
    )

    assert response.json()["needs_review"] is False
    db.refresh(application)
    assert application.needs_review is False


def test_patch_with_the_same_status_confirms_it_without_an_event(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db, needs_review=True)

    response = client.patch(
        f"/applications/{application.id}", json={"status": "acknowledged"}, headers=auth_headers
    )

    assert response.status_code == 200
    db.refresh(application)
    assert application.needs_review is False
    assert application.last_event_at == RECEIVED_AT
    assert db.scalars(select(StatusEvent)).all() == []


def test_patch_company_updates_the_company_key(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db, "Unknown", company_key="", needs_review=True)

    response = client.patch(
        f"/applications/{application.id}", json={"company": "  Globex Inc. "}, headers=auth_headers
    )

    assert response.json()["company"] == "Globex Inc."
    db.refresh(application)
    assert application.company == "Globex Inc."
    assert application.company_key == "globex"
    # Only a status, or the flag itself, clears the flag.
    assert application.needs_review is True
    assert db.scalars(select(StatusEvent)).all() == []


def test_patch_role_sets_and_clears_it(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db)
    url = f"/applications/{application.id}"

    assert client.patch(url, json={"role": "Data Engineer"}, headers=auth_headers).json()[
        "role"
    ] == ("Data Engineer")
    assert client.patch(url, json={"role": None}, headers=auth_headers).json()["role"] is None

    db.refresh(application)
    assert application.role is None
    assert application.company == "Acme Corp"


def test_patch_needs_review_sets_the_flag(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db, needs_review=True)
    url = f"/applications/{application.id}"

    cleared = client.patch(url, json={"needs_review": False}, headers=auth_headers)
    assert cleared.json()["needs_review"] is False
    assert cleared.json()["status"] == "acknowledged"

    flagged = client.patch(url, json={"needs_review": True}, headers=auth_headers)
    assert flagged.json()["needs_review"] is True
    assert db.scalars(select(StatusEvent)).all() == []


def test_patch_can_change_every_field_at_once(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db)

    response = client.patch(
        f"/applications/{application.id}",
        json={"status": "update", "company": "Globex", "role": "QA", "needs_review": True},
        headers=auth_headers,
    )

    body = response.json()
    assert (body["status"], body["company"], body["role"]) == ("update", "Globex", "QA")
    # The explicit flag wins over the status clearing it.
    assert body["needs_review"] is True


def test_patch_with_no_fields_changes_nothing(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db, role="QA", needs_review=True)

    response = client.patch(f"/applications/{application.id}", json={}, headers=auth_headers)

    assert response.status_code == 200
    db.refresh(application)
    assert (application.company, application.role, application.status) == (
        "Acme Corp",
        "QA",
        "acknowledged",
    )
    assert application.needs_review is True


@pytest.mark.parametrize(
    "body",
    [
        {"status": "hired"},
        {"status": None},
        {"company": "   "},
        {"company": None},
        {"needs_review": None},
        {"needs_review": "maybe"},
        {"role": "x" * 201},
    ],
)
def test_patch_rejects_bad_values(
    client: TestClient, db: Session, auth_headers: Headers, body: dict[str, object]
) -> None:
    application = add_application(db)

    response = client.patch(f"/applications/{application.id}", json=body, headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"
    db.refresh(application)
    assert (application.company, application.status) == ("Acme Corp", "acknowledged")


def test_patch_of_an_unknown_id_is_404(client: TestClient, auth_headers: Headers) -> None:
    response = client.patch(
        f"/applications/{uuid.uuid4()}", json={"status": "rejected"}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- POST /applications/{id}/reprint


def texts(job: PrintJob) -> list[str]:
    return [line["text"] for line in job.payload["lines"]]


def test_reprint_queues_the_receipt_of_the_current_status(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    account = add_account(db)
    application = add_application(db, role="Backend Developer", status="rejected")
    email = add_email(
        db,
        account,
        "rejection",
        application_id=application.id,
        subject="Your application",
        confidence=0.92,
    )
    add_event(db, application, email_id=email.id)

    response = client.post(f"/applications/{application.id}/reprint", headers=auth_headers)

    assert response.status_code == 201
    job = db.scalars(select(PrintJob)).one()
    assert response.json() == {"job_id": str(job.id)}
    assert job.status_event_id is None
    assert job.application_id == application.id
    assert job.state == JobState.PENDING
    lines = texts(job)
    assert "Acme Corp" in lines
    assert "Role: Backend Developer" in lines
    assert "REJECTED" in lines
    assert "Your application" in lines
    assert "match 92%" in lines
    assert RECEIVED_AT.strftime("%Y-%m-%d %H:%M") in lines


def test_reprint_after_a_manual_change_has_no_email_lines(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    account = add_account(db)
    application = add_application(db)
    email = add_email(db, account, "ack", application_id=application.id, confidence=0.9)
    add_event(db, application, email_id=email.id)
    url = f"/applications/{application.id}"
    client.patch(url, json={"status": "replied", "company": "Globex"}, headers=auth_headers)

    response = client.post(f"{url}/reprint", headers=auth_headers)

    assert response.status_code == 201
    lines = texts(db.scalars(select(PrintJob)).one())
    assert "Globex" in lines
    assert "REPLIED" in lines
    assert email.subject not in lines
    assert not any(line.startswith("match") for line in lines)


def test_reprint_works_for_an_application_with_no_events(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db)

    response = client.post(f"/applications/{application.id}/reprint", headers=auth_headers)

    assert response.status_code == 201
    assert "ACKNOWLEDGED" in texts(db.scalars(select(PrintJob)).one())


def test_reprint_is_409_while_one_is_pending(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db)
    url = f"/applications/{application.id}/reprint"
    client.post(url, headers=auth_headers)

    response = client.post(url, headers=auth_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REPRINT_PENDING"
    assert len(db.scalars(select(PrintJob)).all()) == 1


def test_reprint_is_allowed_again_once_the_first_was_claimed(
    client: TestClient, db: Session, auth_headers: Headers, device_headers: Headers
) -> None:
    application = add_application(db)
    url = f"/applications/{application.id}/reprint"
    first = client.post(url, headers=auth_headers).json()["job_id"]
    assert client.get("/device/jobs/next", headers=device_headers).json()["id"] == first

    response = client.post(url, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["job_id"] != first


def test_a_pending_reprint_does_not_block_other_applications(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    first = add_application(db, "Acme")
    second = add_application(db, "Globex")
    client.post(f"/applications/{first.id}/reprint", headers=auth_headers)

    response = client.post(f"/applications/{second.id}/reprint", headers=auth_headers)

    assert response.status_code == 201


def test_a_pending_status_receipt_does_not_block_a_reprint(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    application = add_application(db)
    event = add_event(db, application)
    db.add(PrintJob(payload={"lines": []}, status_event_id=event.id))
    db.commit()

    response = client.post(f"/applications/{application.id}/reprint", headers=auth_headers)

    assert response.status_code == 201


def test_reprint_of_an_unknown_id_is_404(
    client: TestClient, db: Session, auth_headers: Headers
) -> None:
    response = client.post(f"/applications/{uuid.uuid4()}/reprint", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert db.scalars(select(PrintJob)).all() == []


def test_a_reprint_prints_like_any_other_job(
    client: TestClient,
    db: Session,
    auth_headers: Headers,
    device: Device,
    device_headers: Headers,
) -> None:
    application = add_application(db)
    job_id = client.post(f"/applications/{application.id}/reprint", headers=auth_headers).json()[
        "job_id"
    ]

    receipt = client.get("/device/jobs/next", headers=device_headers).json()
    acked = client.post(f"/device/jobs/{job_id}/ack", headers=device_headers)

    assert receipt["id"] == job_id
    assert acked.json() == {"id": job_id, "state": "printed"}
