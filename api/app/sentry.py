"""Error reporting. An event leaves without headers, bodies, local variables or credentials."""

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger

from app.config import get_settings
from app.logging import scrub_value

# What is kept of the request. The query string is dropped too: on the Google callback it
# holds the authorisation code.
REQUEST_FIELDS = ("method", "url")


def before_send(event: Any, hint: dict[str, Any]) -> Any:
    request = event.get("request")
    if request:
        event["request"] = {field: request[field] for field in REQUEST_FIELDS if field in request}
    # Messages, exception text and breadcrumbs get the same masking as the logs.
    return scrub_value(event)


def init_sentry() -> bool:
    """Start Sentry when `SENTRY_DSN` is set. Returns whether it is on."""
    settings = get_settings()
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # The variables of a stack frame would carry email text and tokens.
        include_local_variables=False,
        max_request_body_size="never",
        before_send=before_send,
    )
    # An unhandled error is reported once, by the ASGI integration, and not again from its log line.
    ignore_logger("app.errors")
    return True
