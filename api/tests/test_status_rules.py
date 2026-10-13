import pytest

from app.applications.rules import should_apply
from app.classifier.schema import Status

A, R, U, X = Status.ACKNOWLEDGED, Status.REPLIED, Status.UPDATE, Status.REJECTED

# (current, new, applied). None is an application that was just created.
TRANSITIONS = [
    (None, A, True),
    (None, R, True),
    (None, U, True),
    (None, X, True),
    # The same status again: no event, so no second receipt.
    (A, A, False),
    (R, R, False),
    (U, U, False),
    (X, X, False),
    # A late auto-reply.
    (R, A, False),
    (U, A, False),
    (X, A, False),
    # Everything else is applied.
    (A, R, True),
    (A, U, True),
    (A, X, True),
    (R, U, True),
    (R, X, True),
    (U, R, True),
    (U, X, True),
    (X, R, True),
    (X, U, True),
]


@pytest.mark.parametrize(("current", "new", "applied"), TRANSITIONS)
def test_should_apply(current: Status | None, new: Status, applied: bool) -> None:
    assert should_apply(current, new) is applied


def test_the_table_covers_every_pair() -> None:
    pairs = {(current, new) for current, new, _ in TRANSITIONS}

    assert pairs == {(current, new) for current in (None, *Status) for new in Status}
    assert len(TRANSITIONS) == len(pairs)


def test_statuses_read_from_the_database_are_plain_strings() -> None:
    assert should_apply("replied", Status.REJECTED)
    assert not should_apply("replied", Status.REPLIED)
    assert not should_apply("replied", Status.ACKNOWLEDGED)
