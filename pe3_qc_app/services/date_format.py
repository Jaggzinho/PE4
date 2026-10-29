from __future__ import annotations

from datetime import date

QT_DATE_FMT = "dd/MM/yyyy"
PY_DATE_FMT = "%d/%m/%Y"


def format_date(d: date | None, *, empty: str = "") -> str:
    if d is None:
        return empty
    return d.strftime(PY_DATE_FMT)

