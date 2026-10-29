from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pe3_qc_app.services.chart_data import fetch_tolerance


@dataclass(frozen=True)
class QcFailureRow:
    property_name: str
    actual_value: str


@dataclass(frozen=True)
class QcFailureContext:
    test_id: int
    material_code: str
    request_date: date | None


def fetch_alarm_tolerance_failures(con, *, test_id: int) -> tuple[QcFailureContext, list[QcFailureRow]]:
    """
    Returns QC properties for a test that fall outside ALARM tolerances.
    Only properties with a tolerance configured (material-specific, else global) are evaluated.
    """
    tid = int(test_id)
    row = con.execute(
        """
        SELECT t.material_id, mat.code, t.request_date
        FROM tests t
        JOIN materials mat ON mat.material_id = t.material_id
        WHERE t.test_id = ? AND t.deleted_at IS NULL
        """,
        [tid],
    ).fetchone()
    if row is None:
        raise ValueError("Test not found.")
    material_id, material_code, request_date = row
    if material_id is None:
        raise ValueError("Test has no material.")
    mid = int(material_id)

    mrows = con.execute(
        """
        SELECT
            p.name AS property_name,
            m.property_id,
            COALESCE(CAST(m.value_num AS VARCHAR), m.value_text) AS value_text,
            COALESCE(
                m.value_num,
                TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
            ) AS value_num
        FROM measurements m
        JOIN properties p ON p.property_id = m.property_id
        WHERE m.test_id = ?
        ORDER BY p.name, m.measurement_id DESC
        """,
        [tid],
    ).fetchall()

    failures: list[QcFailureRow] = []
    for prop_name, prop_id, value_text, value_num in mrows:
        if prop_id is None:
            continue
        tol = fetch_tolerance(con, property_id=int(prop_id), material_id=mid)
        if tol is None:
            continue
        if value_num is None:
            continue
        alarm_low = tol.get("alarm_low")
        alarm_high = tol.get("alarm_high")
        if alarm_low is None and alarm_high is None:
            continue
        v = float(value_num)
        failed = (alarm_low is not None and v < float(alarm_low)) or (alarm_high is not None and v > float(alarm_high))
        if not failed:
            continue
        actual = (str(value_text) if value_text is not None else str(v))
        failures.append(QcFailureRow(property_name=str(prop_name), actual_value=actual))

    ctx = QcFailureContext(test_id=tid, material_code=str(material_code), request_date=request_date)
    return ctx, failures

