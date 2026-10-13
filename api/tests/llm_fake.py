"""A stand-in for the OpenAI client, so no test touches the network."""

import json
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from app.classifier import llm

REQUEST = httpx2.Request("POST", "http://llm.invalid/v1/chat/completions")


def status_error(status: int) -> openai.APIStatusError:
    """The error the library raises for this HTTP status."""
    kinds = {
        400: openai.BadRequestError,
        401: openai.AuthenticationError,
        403: openai.PermissionDeniedError,
        429: openai.RateLimitError,
    }
    kind = kinds.get(status, openai.InternalServerError)
    return kind("provider said no", response=httpx2.Response(status, request=REQUEST), body=None)


def timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=REQUEST)


def answer(**fields: Any) -> str:
    """A valid classification as the AI would write it; keyword arguments override fields."""
    return json.dumps(
        {
            "is_job_related": True,
            "company": "Acme Corp",
            "role": "React Developer",
            "status": "acknowledged",
            "confidence": 0.93,
        }
        | fields
    )


class FakeLLM:
    """Answers each call with the next item of `answers`; an exception is raised instead.

    The calls are recorded in `calls`, and the retry waits in `sleeps`.
    """

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.calls: list[dict[str, Any]] = []
        self.sleeps: list[float] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **params: Any) -> Any:
        self.calls.append(params)
        result = self.answers.pop(0)
        if isinstance(result, Exception):
            raise result
        message = SimpleNamespace(content=result)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def user_messages(self) -> list[str]:
        return [call["messages"][1]["content"] for call in self.calls]


def use_llm(monkeypatch: pytest.MonkeyPatch, *answers: Any) -> FakeLLM:
    """Make the adapter talk to a fake with these answers, and skip the retry wait."""
    fake = FakeLLM(*answers)
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    monkeypatch.setattr(llm.time, "sleep", fake.sleeps.append)
    return fake
