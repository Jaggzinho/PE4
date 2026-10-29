from __future__ import annotations

from datetime import date

import pytest

from pe3_qc_app.services.parse import parse_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-03-30", date(2026, 3, 30)),
        ("30/03/2026", date(2026, 3, 30)),
        ("30-03-2026", date(2026, 3, 30)),
        ("30.03.2026", date(2026, 3, 30)),
        ("9.12.2020", date(2020, 12, 9)),
    ],
)
def test_parse_date_accepts_supported_workbook_formats(raw: str, expected: date) -> None:
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "not a date", "31.02.2026"])
def test_parse_date_rejects_missing_or_invalid_values(raw: object) -> None:
    assert parse_date(raw) is None
