import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import SettingsError, get_settings

REQUEST_ID_HEADER = "X-Request-ID"
MASK = "***"

# A header, dict key or query parameter whose value is a secret.
_SECRET_NAME = (
    r"(?:authorization|(?:set-)?cookie"
    r"|[\w-]*(?:api[-_]?key|device[-_]key|token|secret|password))"
)
_SECRET_NAME_RE = re.compile(_SECRET_NAME, re.IGNORECASE)
# `Authorization: Bearer abc`, `'X-Device-Key': 'abc'`, `refresh_token=abc`.
_NAMED_SECRET_RE = re.compile(
    rf"(?<![\w-])({_SECRET_NAME}[\"']?\s*[:=]\s*[\"']?)(?:(?:Bearer|Basic)\s+)?[^\s\"',;&}}]+",
    re.IGNORECASE,
)
# Values that are secrets whatever they sit next to.
_TOKEN_RES = [
    (re.compile(r"\b(Bearer|Basic)\s+[\w.~+/=-]+", re.IGNORECASE), rf"\1 {MASK}"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]*"), MASK),  # a JWT
    (re.compile(r"\bjats_dk_[\w-]+"), MASK),  # a device key
    (re.compile(r"\bsk-[\w-]{16,}"), MASK),  # an AI provider key
    (re.compile(r"\bya29\.[\w.-]+"), MASK),  # a Google access token
    (re.compile(r"(?<![\w/])1//[\w-]{20,}"), MASK),  # a Google refresh token
    (re.compile(r"(?<![\w/])4/0[\w-]{20,}"), MASK),  # a Google authorisation code
    (re.compile(r"\bgAAAAA[\w-]{20,}=*"), MASK),  # a Fernet token
    (re.compile(r"(://[^/\s:@]+:)[^@\s/]+@"), rf"\1{MASK}@"),  # the password in a URL
]

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

access_logger = logging.getLogger("app.request")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def _configured_secrets() -> list[str]:
    """The secrets this process was started with, so they are caught whatever they look like."""
    try:
        settings = get_settings()
    except SettingsError:
        return []
    values = (
        settings.llm_api_key,
        settings.token_enc_key,
        settings.state_secret,
        settings.google_client_secret,
    )
    # A short value would also mask ordinary words.
    return [value for value in values if len(value) >= 8]


def scrub(text: str) -> str:
    """Replace anything that looks like a credential with `***`."""
    for secret in _configured_secrets():
        text = text.replace(secret, MASK)
    text = _NAMED_SECRET_RE.sub(rf"\1{MASK}", text)
    for pattern, replacement in _TOKEN_RES:
        text = pattern.sub(replacement, text)
    return text


def scrub_value(value: Any) -> Any:
    """`scrub()` for the strings inside dicts and lists. A secret-named key loses its value."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, dict):
        return {
            key: MASK if _SECRET_NAME_RE.fullmatch(str(key)) else scrub_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [scrub_value(item) for item in value]
    return value


class SecretScrubFilter(logging.Filter):
    """Masks credentials in the message, the data fields and the traceback of every record."""

    _formatter = logging.Formatter()

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub(record.getMessage())
        record.args = None
        if getattr(record, "data", None):
            record.data = scrub_value(record.data)
        if record.exc_info:
            # Formatters use this text instead of formatting the exception again.
            record.exc_text = scrub(self._formatter.formatException(record.exc_info))
        if record.stack_info:
            record.stack_info = scrub(record.stack_info)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            line["request_id"] = request_id
        # Fields passed as extra={"data": {...}} sit next to the message, so they can be searched.
        for key, value in (getattr(record, "data", None) or {}).items():
            line.setdefault(key, value)
        if record.exc_info:
            line["exception"] = record.exc_text or self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def build_handler(stream: TextIO) -> logging.Handler:
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    handler.addFilter(SecretScrubFilter())
    return handler


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers = [build_handler(sys.stdout)]
    root.setLevel(level)

    # Send uvicorn's own logs through the JSON handler too.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # RequestIdMiddleware writes the access line, so uvicorn's is turned off.
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.propagate = False


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        # Not reset afterwards: each request runs in its own task, and the
        # catch-all error handler still needs the id after this returns.
        request_id_var.set(request_id)
        status = 500
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            access_logger.info(
                "%s %s %s %.1fms", scope["method"], scope["path"], status, duration_ms
            )
