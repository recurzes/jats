"""A stand-in for the Gmail service object, so no test touches the network."""

import json
from pathlib import Path
from typing import Any

import httplib2
from googleapiclient.errors import HttpError

FIXTURES = Path(__file__).parent / "fixtures" / "gmail"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def http_error(status: int, reason: str | None = None) -> HttpError:
    errors = [{"reason": reason, "message": "nope"}] if reason else []
    body = {"error": {"code": status, "message": "nope", "errors": errors}}
    return HttpError(httplib2.Response({"status": status}), json.dumps(body).encode())


def message(message_id: str, **fields: Any) -> dict[str, Any]:
    """A copy of the plain fixture under another id."""
    return load_fixture("plain") | {"id": message_id, "threadId": f"thread-{message_id}"} | fields


class FakeRequest:
    """A Gmail API request that answers with a value or raises an error."""

    def __init__(self, result: Any) -> None:
        self.result = result

    def execute(self) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeGmail:
    """Answers the calls the sync makes, and records them in `calls`.

    `list_pages` and `history_pages` are served one page per call; an exception in place of a
    page, or as `profile`, is raised instead.
    """

    def __init__(
        self,
        messages: list[dict[str, Any]] | None = None,
        list_pages: list[Any] | None = None,
        history_pages: list[Any] | None = None,
        profile: Any = None,
    ) -> None:
        self.stored = {item["id"]: item for item in messages or []}
        self.list_pages = list_pages
        self.history_pages = history_pages or [{"historyId": "100"}]
        self.profile = profile or {"emailAddress": "me@example.com", "historyId": "100"}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def users(self) -> "_Users":
        return _Users(self)

    def called(self, name: str) -> list[dict[str, Any]]:
        return [params for call, params in self.calls if call == name]


class _Users:
    def __init__(self, gmail: FakeGmail) -> None:
        self.gmail = gmail

    def getProfile(self, **params: Any) -> FakeRequest:  # noqa: N802
        self.gmail.calls.append(("getProfile", params))
        return FakeRequest(self.gmail.profile)

    def messages(self) -> "_Messages":
        return _Messages(self.gmail)

    def history(self) -> "_History":
        return _History(self.gmail)


class _Messages:
    def __init__(self, gmail: FakeGmail) -> None:
        self.gmail = gmail

    def list(self, **params: Any) -> FakeRequest:
        self.gmail.calls.append(("messages.list", params))
        if self.gmail.list_pages is None:
            # Gmail lists the newest message first.
            ids = [{"id": message_id} for message_id in reversed(self.gmail.stored)]
            return FakeRequest({"messages": ids} if ids else {})
        return FakeRequest(_page(self.gmail.list_pages, params.get("pageToken")))

    def get(self, **params: Any) -> FakeRequest:
        self.gmail.calls.append(("messages.get", params))
        found = self.gmail.stored.get(params["id"])
        return FakeRequest(found if found is not None else http_error(404))


class _History:
    def __init__(self, gmail: FakeGmail) -> None:
        self.gmail = gmail

    def list(self, **params: Any) -> FakeRequest:
        self.gmail.calls.append(("history.list", params))
        return FakeRequest(_page(self.gmail.history_pages, params.get("pageToken")))


def _page(pages: list[Any], token: str | None) -> Any:
    return pages[int(token) if token else 0]


def added(*message_ids: str, labels: list[str] | None = None) -> dict[str, Any]:
    """One history record that adds these messages."""
    return {
        "id": "1",
        "messagesAdded": [
            {"message": {"id": message_id, "labelIds": labels or ["INBOX"]}}
            for message_id in message_ids
        ],
    }
