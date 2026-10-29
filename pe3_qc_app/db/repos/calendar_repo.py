from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CalendarTestRow:
    test_id: int
    material_id: int
    material_code: str
    material_desc: str | None
    lastrina_code: str | None
    prod_date: date


def list_tests_by_prod_date_range(
    con,
    *,
    date_from: date,
    date_to: date,
) -> list[CalendarTestRow]:
    """
    Calendar listing: returns non-deleted tests that have a prod_date within the
    inclusive [date_from, date_to] window.
    """
    rows = con.execute(
        """
        SELECT
            t.test_id,
            t.material_id,
            mat.code,
            mat.description,
            mat.lastrina_code,
            t.prod_date
        FROM tests t
        JOIN materials mat ON mat.material_id = t.material_id
        WHERE
            t.deleted_at IS NULL
            AND t.prod_date IS NOT NULL
            AND t.prod_date <> DATE '1900-01-01'
            AND t.prod_date >= ?
            AND t.prod_date <= ?
        ORDER BY t.prod_date ASC, mat.code ASC, t.test_id ASC
        """,
        [date_from, date_to],
    ).fetchall()
    out: list[CalendarTestRow] = []
    for tid, mid, code, desc, las_code, prod_date in rows:
        if prod_date is None:
            continue
        out.append(
            CalendarTestRow(
                test_id=int(tid),
                material_id=int(mid),
                material_code=str(code),
                material_desc=(str(desc) if desc is not None else None),
                lastrina_code=(str(las_code) if las_code is not None else None),
                prod_date=prod_date,
            )
        )
    return out
