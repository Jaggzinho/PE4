from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SinotticoDashboardRow:
    item_id: int
    machine_code: str | None
    excel_code: str | None
    description: str | None
    material_id: int | None
    material_code: str | None
    lastrina_code: str | None
    last_request_date: date | None


def list_dashboard_rows(con) -> list[SinotticoDashboardRow]:
    rows = con.execute(
        """
        WITH last_req AS (
            SELECT material_id, MAX(request_date) AS last_request_date
            FROM tests
            WHERE deleted_at IS NULL
            GROUP BY material_id
        )
        SELECT
            s.item_id,
            s.machine_code,
            s.excel_code,
            s.description,
            s.material_id,
            m.code AS material_code,
            m.lastrina_code,
            lr.last_request_date
        FROM sinottico_items s
        LEFT JOIN materials m ON m.material_id = s.material_id
        LEFT JOIN last_req lr ON lr.material_id = s.material_id
        WHERE s.active
        ORDER BY COALESCE(s.sort_order, 999999), s.item_id
        """
    ).fetchall()
    out: list[SinotticoDashboardRow] = []
    for r in rows:
        out.append(
            SinotticoDashboardRow(
                item_id=int(r[0]),
                machine_code=(str(r[1]) if r[1] is not None else None),
                excel_code=(str(r[2]) if r[2] is not None else None),
                description=(str(r[3]) if r[3] is not None else None),
                material_id=(int(r[4]) if r[4] is not None else None),
                material_code=(str(r[5]) if r[5] is not None else None),
                lastrina_code=(str(r[6]) if r[6] is not None else None),
                last_request_date=r[7],
            )
        )
    return out

