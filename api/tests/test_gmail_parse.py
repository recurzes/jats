from datetime import UTC, datetime

from gmail_fake import FakeGmail, load_fixture, message

from app.gmail.parse import ParsedEmail, fetch_message, html_to_text, parse_message

# --- the three fixtures


def test_parse_a_plain_message() -> None:
    parsed = parse_message(load_fixture("plain"))

    assert parsed == ParsedEmail(
        gmail_message_id="18f0a1b2c3d4e5f6",
        thread_id="18f0a1b2c3d4e5f6",
        from_address="careers@acme.example",
        from_domain="acme.example",
        subject="We received your application",
        # Gmail sends the snippet HTML-escaped.
        snippet="Hi Lance, Thank you for applying to the React Developer position at Acme Corp. "
        "We've received your application",
        received_at=datetime(2026, 10, 13, 8, 0, tzinfo=UTC),
        body=parsed.body,
    )
    assert parsed.body.startswith("Hi Lance,")
    assert parsed.body.endswith("The Acme Corp hiring team")
    assert "Thank you for applying to the React Developer position" in parsed.body


def test_parse_a_multipart_message() -> None:
    parsed = parse_message(load_fixture("multipart"))

    # Encoded headers are decoded, and the address is lowercased.
    assert parsed.from_address == "maria.lopez@globex.example"
    assert parsed.from_domain == "globex.example"
    assert parsed.subject == "Interview invitation – Backend Engineer"
    assert parsed.thread_id == "18f0a9998887776f"
    assert parsed.received_at == datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    # The text/plain part wins over the HTML one, and the attachment is left out.
    assert parsed.body.startswith("Hello Lance,")
    assert "Please pick a time: https://calendar.example/globex" in parsed.body
    assert parsed.body.endswith("María")
    assert "<p>" not in parsed.body


def test_parse_an_html_only_message() -> None:
    parsed = parse_message(load_fixture("html_only"))

    assert parsed.from_address == "no-reply@indeed.com"
    assert parsed.from_domain == "indeed.com"
    assert parsed.subject == "An update on your application to Initech"
    assert parsed.body.splitlines() == [
        "Application update",
        "Indeed",
        "Hi Lance,",
        "Unfortunately, Initech has decided not to move forward with your application for"
        " Frontend Developer .",
        "Applied on: 2 October 2026",
        "Location: Remote",
        "Job Frontend Developer",
        "You are receiving this email because you applied on Indeed.",
    ]


# --- parse_message


def test_snippet_is_cut_to_500_characters() -> None:
    parsed = parse_message(message("a", snippet="x" * 800))

    assert parsed.snippet == "x" * 500


def test_missing_headers_and_body_parse_to_empty_values() -> None:
    bare = {"id": "a", "threadId": "t", "internalDate": "0", "payload": {"mimeType": "text/plain"}}

    parsed = parse_message(bare)

    assert parsed.from_address == ""
    assert parsed.from_domain == ""
    assert parsed.subject == ""
    assert parsed.snippet == ""
    assert parsed.body == ""
    assert parsed.received_at == datetime(1970, 1, 1, tzinfo=UTC)


def test_an_empty_plain_part_falls_back_to_the_html_part() -> None:
    multipart = load_fixture("multipart")
    alternative = multipart["payload"]["parts"][0]["parts"]
    alternative[0]["body"] = {"size": 0}

    parsed = parse_message(multipart)

    assert parsed.body.splitlines() == [
        "Hello Lance,",
        "We would like to invite you to an interview for the Backend Engineer role.",
    ]


# --- html_to_text


def test_html_to_text_drops_script_and_style() -> None:
    html = "<style>p { color: red; }</style><script>alert('x')</script><p>Hello</p>"

    assert html_to_text(html) == "Hello"


def test_html_to_text_keeps_line_breaks_for_br_p_and_div() -> None:
    html = "<div>one<br>two</div><p>three</p><p>four</p><span>five</span> <span>six</span>"

    assert html_to_text(html) == "one\ntwo\nthree\nfour\nfive six"


def test_html_to_text_collapses_whitespace() -> None:
    html = "<p>  spread \n\n  over\tseveral   lines </p>\n\n\n<p>&nbsp;</p><p>next</p>"

    assert html_to_text(html) == "spread over several lines\nnext"


# --- fetch_message


def test_fetch_message_fetches_and_parses() -> None:
    gmail = FakeGmail(messages=[load_fixture("plain")])

    parsed = fetch_message(gmail, "18f0a1b2c3d4e5f6")

    assert parsed is not None
    assert parsed.subject == "We received your application"
    assert gmail.called("messages.get")[0]["format"] == "full"


def test_fetch_message_returns_none_for_a_deleted_message() -> None:
    assert fetch_message(FakeGmail(), "gone") is None
