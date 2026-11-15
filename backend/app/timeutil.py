from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC 'now' (same values as the deprecated datetime.utcnow(), without the warning).

    Timestamps are stored in SQLite as naive ISO strings, so this keeps the existing format.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
