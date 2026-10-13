import textwrap
import unicodedata

ELLIPSIS = "..."


def sanitize_text(text: str) -> str:
    """Reduce untrusted text to one line of printable ASCII.

    Control characters (including ESC, 0x1B) and non-ASCII are dropped, so email text can
    never reach the printer as a command. Whitespace runs, newlines included, become one space.
    """
    # NFKD splits accented letters into a base letter plus a mark, so "é" keeps its "e".
    decomposed = unicodedata.normalize("NFKD", text)
    spaced = (" " if char.isspace() else char for char in decomposed)
    printable = "".join(char for char in spaced if " " <= char <= "~")
    return " ".join(printable.split())


def wrap(text: str, width: int, max_lines: int | None = None) -> list[str]:
    """Sanitize and split into lines of at most `width`; a longer word is broken.

    With `max_lines`, the rest is cut and the last line ends in "...".
    """
    return textwrap.wrap(
        sanitize_text(text),
        width=width,
        max_lines=max_lines,
        placeholder=ELLIPSIS,
        break_on_hyphens=False,
    )


def truncate(text: str, width: int) -> str:
    """Sanitize and cut to one line of at most `width`, ending in "..." when cut."""
    clean = sanitize_text(text)
    if len(clean) <= width:
        return clean
    if width <= len(ELLIPSIS):
        return clean[:width]
    return clean[: width - len(ELLIPSIS)].rstrip() + ELLIPSIS
