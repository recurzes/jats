from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from gmail_fake import FakeGmail, added, http_error, message
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from app.gmail import client
from app.gmail.client import (
    GmailHistoryExpiredError,
    GmailRateLimitError,
    get_current_history_id,
    get_message,
    list_message_ids,
    list_new_message_ids_since,
)

# --- list_message_ids


def test_list_message_ids_asks_for_the_last_7_days() -> None:
    gmail = FakeGmail(list_pages=[{"messages": [{"id": "b"}, {"id": "a"}]}])

    assert list_message_ids(gmail) == ["b", "a"]
    assert gmail.called("messages.list") == [
        {"userId": "me", "q": "newer_than:7d", "pageToken": None}
    ]


def test_list_message_ids_follows_next_page_token() -> None:
    gmail = FakeGmail(
        list_pages=[
            {"messages": [{"id": "c"}], "nextPageToken": "1"},
            {"messages": [{"id": "b"}], "nextPageToken": "2"},
            {"messages": [{"id": "a"}]},
        ]
    )

    assert list_message_ids(gmail, query="newer_than:1d") == ["c", "b", "a"]
    calls = gmail.called("messages.list")
    assert [call["pageToken"] for call in calls] == [None, "1", "2"]
    assert {call["q"] for call in calls} == {"newer_than:1d"}


def test_list_message_ids_of_an_empty_inbox() -> None:
    # Gmail leaves the "messages" key out when nothing matches.
    assert list_message_ids(FakeGmail(list_pages=[{"resultSizeEstimate": 0}])) == []


# --- get_current_history_id


def test_get_current_history_id() -> None:
    gmail = FakeGmail(profile={"emailAddress": "me@example.com", "historyId": "4821"})

    assert get_current_history_id(gmail) == "4821"
    assert gmail.called("getProfile") == [{"userId": "me"}]


# --- list_new_message_ids_since


def test_list_new_message_ids_since_returns_added_ids_and_the_newest_history_id() -> None:
    gmail = FakeGmail(
        history_pages=[{"history": [added("a"), added("b", "c")], "historyId": "150"}]
    )

    assert list_new_message_ids_since(gmail, "100") == (["a", "b", "c"], "150")
    assert gmail.called("history.list") == [
        {
            "userId": "me",
            "startHistoryId": "100",
            "historyTypes": ["messageAdded"],
            "pageToken": None,
        }
    ]


def test_list_new_message_ids_since_follows_pages_and_drops_repeats() -> None:
    gmail = FakeGmail(
        history_pages=[
            {"history": [added("a", "b")], "historyId": "140", "nextPageToken": "1"},
            {"history": [added("b"), added("c")], "historyId": "160", "nextPageToken": "2"},
            {"history": [added("a", "d")], "historyId": "180"},
        ]
    )

    assert list_new_message_ids_since(gmail, "100") == (["a", "b", "c", "d"], "180")
    assert [call["pageToken"] for call in gmail.called("history.list")] == [None, "1", "2"]


@pytest.mark.parametrize("label", ["SPAM", "TRASH"])
def test_list_new_message_ids_since_ignores_spam_and_trash(label: str) -> None:
    history = [added("a"), added("junk", labels=[label, "UNREAD"]), added("b")]
    gmail = FakeGmail(history_pages=[{"history": history, "historyId": "150"}])

    assert list_new_message_ids_since(gmail, "100") == (["a", "b"], "150")


def test_list_new_message_ids_since_with_nothing_new() -> None:
    # Gmail leaves the "history" key out when nothing changed.
    gmail = FakeGmail(history_pages=[{"historyId": "100"}])

    assert list_new_message_ids_since(gmail, "100") == ([], "100")


def test_an_expired_history_id_raises_history_expired() -> None:
    gmail = FakeGmail(history_pages=[http_error(404)])

    with pytest.raises(GmailHistoryExpiredError):
        list_new_message_ids_since(gmail, "1")


def test_other_history_errors_keep_their_type() -> None:
    with pytest.raises(GmailRateLimitError):
        list_new_message_ids_since(FakeGmail(history_pages=[http_error(429)]), "1")
    with pytest.raises(HttpError):
        list_new_message_ids_since(FakeGmail(history_pages=[http_error(400)]), "1")


# --- get_message


def test_get_message_asks_for_the_full_format() -> None:
    gmail = FakeGmail(messages=[message("a")])

    assert get_message(gmail, "a")["id"] == "a"
    assert gmail.called("messages.get") == [{"userId": "me", "id": "a", "format": "full"}]


def test_get_message_returns_none_for_a_deleted_message() -> None:
    assert get_message(FakeGmail(), "gone") is None


# --- against the real client library


def test_the_real_gmail_client_accepts_these_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fake accepts any parameter name; the real request builders do not."""
    urls: list[str] = []

    def execute(request: Any) -> dict[str, str]:
        urls.append(request.uri)
        return {"historyId": "9"}

    monkeypatch.setattr(client, "execute", execute)
    service = client.build_service(Credentials(token="access-token"))

    list_message_ids(service)
    list_new_message_ids_since(service, "100")
    get_message(service, "abc")
    get_current_history_id(service)

    paths = [urlsplit(url).path for url in urls]
    queries = [parse_qs(urlsplit(url).query) for url in urls]
    assert paths == [
        "/gmail/v1/users/me/messages",
        "/gmail/v1/users/me/history",
        "/gmail/v1/users/me/messages/abc",
        "/gmail/v1/users/me/profile",
    ]
    assert queries[0]["q"] == ["newer_than:7d"]
    assert "pageToken" not in queries[0]
    assert queries[1]["startHistoryId"] == ["100"]
    assert queries[1]["historyTypes"] == ["messageAdded"]
    assert queries[2]["format"] == ["full"]
