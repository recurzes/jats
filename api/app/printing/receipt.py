import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.config import get_settings
from app.printing.sanitizer import sanitize_text, truncate, wrap

Align = Literal["left", "center", "right"]


class ReceiptLine(BaseModel):
    text: str
    align: Align = "left"
    bold: bool = False


class Receipt(BaseModel):
    # The print job id. Empty until the receipt is queued.
    id: uuid.UUID | None = None
    lines: list[ReceiptLine]
    cut: bool = True


def render_status_receipt(
    company: str,
    role: str,
    status: str,
    when: datetime,
    subject: str,
    confidence: float | None = None,
    width: int | None = None,
) -> Receipt:
    """Lay out one status change. Every text field goes through the sanitizer.

    `confidence` is None for a status that was set by hand, which leaves the match line out.
    """
    width = width or get_settings().receipt_width
    rule = ReceiptLine(text="-" * width)
    match_lines = []
    if confidence is not None:
        percent = round(min(max(confidence, 0.0), 1.0) * 100)
        match_lines = [ReceiptLine(text=f"match {percent}%")]
    role_lines = wrap(f"Role: {role}", width, max_lines=2) if sanitize_text(role) else []

    lines = [
        ReceiptLine(text="JATS", align="center", bold=True),
        ReceiptLine(text="STATUS UPDATE", align="center", bold=True),
        rule,
        *(ReceiptLine(text=text) for text in wrap(company, width, max_lines=2) or ["Unknown"]),
        *(ReceiptLine(text=text) for text in role_lines),
        rule,
        ReceiptLine(text=truncate(status, width).upper(), align="center", bold=True),
        rule,
        ReceiptLine(text=when.strftime("%Y-%m-%d %H:%M")),
        *(ReceiptLine(text=text) for text in wrap(subject, width, max_lines=2)),
        *match_lines,
    ]
    return Receipt(lines=lines, cut=True)
