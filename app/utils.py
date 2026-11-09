"""Shared utility helpers."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime.

    Drop-in replacement for the deprecated ``datetime.utcnow()``; keeps the
    naive-UTC value that DATETIME columns and existing comparisons expect.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
