"""The AI adapter: the only module that calls the AI provider."""

import logging
import time
from functools import lru_cache

from openai import APIConnectionError, APIStatusError, OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 2


class LLMError(Exception):
    """Any failure talking to the AI provider."""


class LLMUnavailable(LLMError):
    """The provider is rate limiting, failing or not answering; try again later."""


class LLMAuthError(LLMError):
    """The provider refused the API key."""


class LLMRejected(LLMError):
    """The provider refused this request, for example a 400. Sending it again will not help."""


@lru_cache
def get_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        # Empty falls back to the library default, which is OpenAI itself.
        base_url=settings.llm_base_url or None,
        # Local providers take any key, but the library refuses an empty one.
        api_key=settings.llm_api_key or "unset",
        timeout=settings.llm_timeout_seconds,
        # The one retry is done below, so the wait and the errors are ours.
        max_retries=0,
    )


def _complete(system: str, user: str) -> str:
    """One call. The messages below never include the provider's answer or the email text."""
    try:
        response = get_client().chat.completions.create(
            model=get_settings().llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except APIStatusError as exc:
        status = exc.status_code
        if status in (401, 403):
            raise LLMAuthError(f"The AI provider refused the API key ({status})") from None
        if status == 429 or status >= 500:
            raise LLMUnavailable(f"The AI provider is unavailable ({status})") from None
        raise LLMRejected(f"The AI provider refused the request ({status})") from None
    except APIConnectionError as exc:
        # Timeouts are connection errors too.
        raise LLMUnavailable(f"The AI provider did not answer ({type(exc).__name__})") from None
    return response.choices[0].message.content or ""


def chat_json(system: str, user: str) -> str:
    """Ask the model for a JSON object and return its text, not yet parsed or checked.

    Retries once on a 429, a 5xx or a timeout, then raises `LLMUnavailable`.
    """
    try:
        return _complete(system, user)
    except LLMUnavailable as exc:
        logger.warning("AI call failed, retrying once: %s", exc)
    time.sleep(RETRY_DELAY_SECONDS)
    return _complete(system, user)
