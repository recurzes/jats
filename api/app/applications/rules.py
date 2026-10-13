from app.classifier.schema import Status


def should_apply(current: str | None, new: str) -> bool:
    """Whether an email saying `new` changes an application whose status is `current`.

    `current` is None for an application that was just created.
    """
    if current == new:
        return False
    # A late auto-reply must not undo a status that came after it.
    if new == Status.ACKNOWLEDGED and current is not None:
        return False
    return True
