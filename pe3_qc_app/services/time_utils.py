from __future__ import annotations

from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    # DuckDB TIMESTAMP is timezone-naive in this app; store UTC but drop tzinfo.
    return datetime.now(UTC).replace(tzinfo=None)

