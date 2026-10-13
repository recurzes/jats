import string

import pytest

from app.printing.sanitizer import sanitize_text, truncate, wrap

WIDTH = 32
PRINTABLE = set(string.ascii_letters + string.digits + string.punctuation + " ")

HOSTILE = [
    "Congrats 🎉 you got it 🚀",
    "line one\nline two\r\nline three\tend",
    "\x1b@Acme\x1bd\x05 Corp\x00\x07",
    "Supercalifragilisticexpialidocious" * 3,
    "Café Zürich — “Senior” Engineer…",
    "",
]


def test_sanitize_drops_emoji() -> None:
    assert sanitize_text("Congrats 🎉 you got it 🚀") == "Congrats you got it"


def test_sanitize_turns_injected_newlines_into_spaces() -> None:
    assert sanitize_text("one\ntwo\r\nthree\tfour") == "one two three four"


def test_sanitize_drops_esc_and_other_control_characters() -> None:
    assert sanitize_text("\x1b@Acme\x1bd\x05 Corp\x00\x07") == "@Acmed Corp"


def test_sanitize_keeps_the_base_letter_of_an_accent() -> None:
    assert sanitize_text("Café Zürich") == "Cafe Zurich"


def test_wrap_breaks_a_very_long_word() -> None:
    lines = wrap("a" * 70, WIDTH)

    assert lines == ["a" * 32, "a" * 32, "a" * 6]


def test_wrap_breaks_between_words() -> None:
    assert wrap("Senior Staff Software Engineer, Platform Team", 20) == [
        "Senior Staff",
        "Software Engineer,",
        "Platform Team",
    ]


def test_wrap_max_lines_ends_with_dots() -> None:
    lines = wrap("one two three four five six seven eight nine ten", 12, max_lines=2)

    assert lines == ["one two", "three..."]


def test_truncate() -> None:
    assert truncate("short", WIDTH) == "short"
    assert truncate("b" * 40, WIDTH) == "b" * 29 + "..."
    assert truncate("abcdef", 2) == "ab"


@pytest.mark.parametrize("text", HOSTILE)
def test_output_is_always_printable_ascii_within_the_width(text: str) -> None:
    outputs = [*wrap(text, WIDTH), *wrap(text, WIDTH, max_lines=2), truncate(text, WIDTH)]

    assert set(sanitize_text(text)) <= PRINTABLE
    for line in outputs:
        assert set(line) <= PRINTABLE
        assert len(line) <= WIDTH
