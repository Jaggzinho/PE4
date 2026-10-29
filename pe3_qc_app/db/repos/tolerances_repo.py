from __future__ import annotations

from dataclasses import dataclass
from pe3_qc_app.services.time_utils import utc_now_naive

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class Tolerance:
    tolerance_id: int
    material_id: int | None
    property_id: int
    warn_low: float | None
    warn_high: float | None
    alarm_low: float | None
    alarm_high: float | None
    reference_value: float | None = None
    warn_low_input: float | None = None
    warn_low_mode: str = "absolute"
    warn_high_input: float | None = None
    warn_high_mode: str = "absolute"
    alarm_low_input: float | None = None
    alarm_low_mode: str = "absolute"
    alarm_high_input: float | None = None
    alarm_high_mode: str = "absolute"
    is_custom: bool = False


def list_tolerances(con) -> list[Tolerance]:
    rows = con.execute(
        """
        SELECT tolerance_id, material_id, property_id, warn_low, warn_high, alarm_low, alarm_high,
               reference_value, warn_low_input, warn_low_mode, warn_high_input, warn_high_mode,
               alarm_low_input, alarm_low_mode, alarm_high_input, alarm_high_mode, is_custom
        FROM tolerances
        ORDER BY property_id, material_id NULLS FIRST, updated_at DESC
        """
    ).fetchall()
    out: list[Tolerance] = []
    for r in rows:
        out.append(
            Tolerance(
                tolerance_id=int(r[0]),
                material_id=(int(r[1]) if r[1] is not None else None),
                property_id=int(r[2]),
                warn_low=(float(r[3]) if r[3] is not None else None),
                warn_high=(float(r[4]) if r[4] is not None else None),
                alarm_low=(float(r[5]) if r[5] is not None else None),
                alarm_high=(float(r[6]) if r[6] is not None else None),
                reference_value=(float(r[7]) if r[7] is not None else None),
                warn_low_input=(float(r[8]) if r[8] is not None else None),
                warn_low_mode=str(r[9] or "absolute"),
                warn_high_input=(float(r[10]) if r[10] is not None else None),
                warn_high_mode=str(r[11] or "absolute"),
                alarm_low_input=(float(r[12]) if r[12] is not None else None),
                alarm_low_mode=str(r[13] or "absolute"),
                alarm_high_input=(float(r[14]) if r[14] is not None else None),
                alarm_high_mode=str(r[15] or "absolute"),
                is_custom=bool(r[16]),
            )
        )
    return out


def upsert_tolerance(
    con,
    *,
    tolerance_id: int | None,
    material_id: int | None,
    property_id: int,
    warn_low: float | None,
    warn_high: float | None,
    alarm_low: float | None,
    alarm_high: float | None,
    reference_value: float | None = None,
    warn_low_input: float | None = None,
    warn_low_mode: str = "absolute",
    warn_high_input: float | None = None,
    warn_high_mode: str = "absolute",
    alarm_low_input: float | None = None,
    alarm_low_mode: str = "absolute",
    alarm_high_input: float | None = None,
    alarm_high_mode: str = "absolute",
) -> int:
    config = [reference_value, warn_low_input, warn_low_mode, warn_high_input, warn_high_mode,
              alarm_low_input, alarm_low_mode, alarm_high_input, alarm_high_mode]
    if tolerance_id is None:
        tolerance_id = new_id()
        con.execute(
            """
            INSERT INTO tolerances(
                tolerance_id, material_id, property_id, warn_low, warn_high, alarm_low, alarm_high, updated_at,
                reference_value, warn_low_input, warn_low_mode, warn_high_input, warn_high_mode,
                alarm_low_input, alarm_low_mode, alarm_high_input, alarm_high_mode, is_custom
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            """,
            [tolerance_id, material_id, int(property_id), warn_low, warn_high, alarm_low, alarm_high, utc_now_naive(), *config],
        )
        return int(tolerance_id)

    con.execute(
        """
        UPDATE tolerances
        SET material_id=?, property_id=?, warn_low=?, warn_high=?, alarm_low=?, alarm_high=?, updated_at=?,
            reference_value=?, warn_low_input=?, warn_low_mode=?, warn_high_input=?, warn_high_mode=?,
            alarm_low_input=?, alarm_low_mode=?, alarm_high_input=?, alarm_high_mode=?, is_custom=TRUE
        WHERE tolerance_id=?
        """,
        [material_id, int(property_id), warn_low, warn_high, alarm_low, alarm_high, utc_now_naive(), *config, int(tolerance_id)],
    )
    return int(tolerance_id)


def delete_tolerance(con, *, tolerance_id: int) -> None:
    con.execute("DELETE FROM tolerances WHERE tolerance_id = ?", [int(tolerance_id)])


def ensure_material_tolerance(
    con,
    *,
    material_id: int,
    property_id: int,
    warn_low: float | None,
    warn_high: float | None,
    alarm_low: float | None,
    alarm_high: float | None,
) -> dict:
    """
    Ensure a material-specific tolerance exists. If present, returns the most recent
    material-specific tolerance for (material_id, property_id). If absent, inserts a new
    row and returns the inserted values.
    """
    row = con.execute(
        """
        SELECT warn_low, warn_high, alarm_low, alarm_high
        FROM tolerances
        WHERE property_id=? AND material_id=?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        [int(property_id), int(material_id)],
    ).fetchone()
    if row:
        return {"warn_low": row[0], "warn_high": row[1], "alarm_low": row[2], "alarm_high": row[3]}

    tolerance_id = new_id()
    con.execute(
        """
        INSERT INTO tolerances(
            tolerance_id, material_id, property_id, warn_low, warn_high, alarm_low, alarm_high, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            int(tolerance_id),
            int(material_id),
            int(property_id),
            warn_low,
            warn_high,
            alarm_low,
            alarm_high,
            utc_now_naive(),
        ],
    )
    return {"warn_low": warn_low, "warn_high": warn_high, "alarm_low": alarm_low, "alarm_high": alarm_high}
