import base64
import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.utils import parseaddr
from typing import Any

from bs4 import BeautifulSoup

from app.gmail.client import get_message

SNIPPET_LENGTH = 500
LINE_BREAK_TAGS = ("p", "div")


@dataclass(frozen=True)
class ParsedEmail:
    gmail_message_id: str
    thread_id: str
    from_address: str
    from_domain: str
    subject: str
    snippet: str
    received_at: datetime
    # For the classifier only. Never written to the database.
    body: str


def html_to_text(markup: str) -> str:
    """Readable text from an HTML body, one line per `br`, `p` and `div`."""
    # Line breaks in the source mean nothing in HTML; the only ones kept are added below.
    soup = BeautifulSoup(re.sub(r"\s+", " ", markup), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(LINE_BREAK_TAGS):
        block.insert_before("\n")
        block.append("\n")
    # The space keeps the text of neighbouring table cells apart.
    lines = (" ".join(line.split()) for line in soup.get_text(" ").split("\n"))
    return "\n".join(line for line in lines if line)


def _header(payload: dict[str, Any], name: str) -> str:
    for header in payload.get("headers", []):
        if header["name"].lower() == name:
            value = header["value"]
            try:
                # Turns "=?UTF-8?B?...?=" into text; plain values pass through unchanged.
                return str(make_header(decode_header(value)))
            except (LookupError, ValueError):
                return value
    return ""


def _decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _texts(part: dict[str, Any], mime_type: str) -> list[str]:
    """The decoded bodies of every part of this type, skipping attachments."""
    if part.get("mimeType") == mime_type and not part.get("filename"):
        data = part.get("body", {}).get("data")
        return [_decode(data)] if data else []
    return [text for child in part.get("parts", []) for text in _texts(child, mime_type)]


def _body(payload: dict[str, Any]) -> str:
    plain = "\n".join(_texts(payload, "text/plain")).strip()
    if plain:
        return plain
    return "\n".join(html_to_text(markup) for markup in _texts(payload, "text/html")).strip()


def parse_message(message: dict[str, Any]) -> ParsedEmail:
    """Turn a Gmail `format=full` message into a ParsedEmail."""
    payload = message.get("payload", {})
    address = parseaddr(_header(payload, "from"))[1].lower()
    return ParsedEmail(
        gmail_message_id=message["id"],
        thread_id=message["threadId"],
        from_address=address,
        from_domain=address.rpartition("@")[2],
        subject=_header(payload, "subject"),
        # Gmail escapes the snippet for HTML.
        snippet=html.unescape(message.get("snippet", ""))[:SNIPPET_LENGTH],
        received_at=datetime.fromtimestamp(int(message["internalDate"]) / 1000, UTC),
        body=_body(payload),
    )


def fetch_message(service: Any, message_id: str) -> ParsedEmail | None:
    """Fetch and parse one message. None when it no longer exists."""
    message = get_message(service, message_id)
    return parse_message(message) if message else None
