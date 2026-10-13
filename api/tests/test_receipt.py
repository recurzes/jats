import uuid
from datetime import datetime

from app.printing.receipt import Receipt, ReceiptLine, render_status_receipt

WIDTH = 32
RULE = "-" * WIDTH


def render(**overrides: object) -> Receipt:
    fields = {
        "company": "Acme Corp",
        "role": "React Developer",
        "status": "Rejected",
        "when": datetime(2026, 10, 13, 9, 5),
        "subject": "Update on your application",
        "confidence": 0.93,
        "width": WIDTH,
    }
    return render_status_receipt(**{**fields, **overrides})


def test_receipt_serialises_to_the_spec_shape() -> None:
    job_id = uuid.uuid4()
    receipt = Receipt(
        id=job_id,
        lines=[
            ReceiptLine(text="STATUS UPDATE", align="center", bold=True),
            ReceiptLine(text="Acme Corp"),
        ],
        cut=True,
    )

    assert receipt.model_dump(mode="json") == {
        "id": str(job_id),
        "lines": [
            {"text": "STATUS UPDATE", "align": "center", "bold": True},
            {"text": "Acme Corp", "align": "left", "bold": False},
        ],
        "cut": True,
    }


def test_render_status_receipt_snapshot() -> None:
    receipt = render()

    assert receipt.cut is True
    assert [(line.text, line.align, line.bold) for line in receipt.lines] == [
        ("JATS", "center", True),
        ("STATUS UPDATE", "center", True),
        (RULE, "left", False),
        ("Acme Corp", "left", False),
        ("Role: React Developer", "left", False),
        (RULE, "left", False),
        ("REJECTED", "center", True),
        (RULE, "left", False),
        ("2026-10-13 09:05", "left", False),
        ("Update on your application", "left", False),
        ("match 93%", "left", False),
    ]


def test_render_sanitizes_and_fits_every_line() -> None:
    receipt = render(
        company="\x1b@Évil Corp 🎉 " + "x" * 80,
        role="Senior Staff Principal Software Engineer\nPlatform and Infrastructure Team",
        status="re\x1bjected" + "!" * 50,
        subject="Re: Fwd: Re: your application to the very long role name at our company " * 3,
    )

    for line in receipt.lines:
        assert line.text.isascii() and line.text.isprintable()
        assert len(line.text) <= WIDTH
    assert receipt.lines[3].text.startswith("@Evil Corp")


def test_render_skips_an_empty_role() -> None:
    texts = [line.text for line in render(company="", role="  ").lines]

    assert "Unknown" in texts
    assert not any(text.startswith("Role:") for text in texts)
