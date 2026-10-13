import pytest

from app.classifier.prefilter import is_candidate
from app.classifier.rules import JOB_BOARD_DOMAINS


@pytest.mark.parametrize(
    ("from_domain", "subject"),
    [
        ("indeed.com", "Lance, new jobs for you"),  # a job board, whatever the subject
        ("mail.onlinejobs.ph", "You have a new message"),  # a subdomain of a job board
        ("acme.example", "We received your application"),
        ("globex.example", "Interview invitation – Backend Engineer"),
        ("initech.example", "Unfortunately we are moving forward with other candidates"),
    ],
)
def test_job_emails_are_candidates(from_domain: str, subject: str) -> None:
    assert is_candidate(from_domain, subject)


@pytest.mark.parametrize(
    ("from_domain", "subject"),
    [
        ("github.com", "[jats] Run failed: api - main"),
        ("bank.example", "Your statement is ready"),
        ("shop.example", "Your order has shipped"),
        ("music.example", "A new composition from an artist you follow"),  # not "position"
        ("notindeed.com", "Weekly newsletter"),  # ends like a job board, but is another domain
    ],
)
def test_other_emails_are_not_candidates(from_domain: str, subject: str) -> None:
    assert not is_candidate(from_domain, subject)


def test_a_reply_from_an_unknown_domain_in_a_known_thread_is_a_candidate() -> None:
    assert not is_candidate("gmail.com", "Re: quick question")
    assert is_candidate("gmail.com", "Re: quick question", in_known_thread=True)


@pytest.mark.parametrize("domain", JOB_BOARD_DOMAINS)
def test_every_listed_job_board_is_a_candidate(domain: str) -> None:
    assert is_candidate(domain, "")
    assert is_candidate(domain.upper(), "")


@pytest.mark.parametrize(
    "subject",
    [
        "Your Application",
        "You APPLIED to Acme",
        "Interviews next week",
        "Candidates wanted",
        "Open positions",
        "Unfortunately...",
    ],
)
def test_keywords_match_any_case_and_word_endings(subject: str) -> None:
    assert is_candidate("acme.example", subject)
