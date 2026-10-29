from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RatingWeightRow:
    property_id: int
    weight: float


@dataclass(frozen=True)
class RatingRuleRow:
    property_id: int
    rule_json: str


def list_weights(con) -> list[RatingWeightRow]:
    rows = con.execute(
        """
        SELECT property_id, weight
        FROM rating_property_weights
        ORDER BY property_id
        """
    ).fetchall()
    return [RatingWeightRow(property_id=int(r[0]), weight=float(r[1])) for r in rows]


def list_rules(con) -> list[RatingRuleRow]:
    rows = con.execute(
        """
        SELECT property_id, rule_json
        FROM rating_property_rules
        ORDER BY property_id
        """
    ).fetchall()
    return [RatingRuleRow(property_id=int(r[0]), rule_json=str(r[1])) for r in rows]


def upsert_weight(con, *, property_id: int, weight: float) -> None:
    w = float(weight)
    if w < 0:
        raise ValueError("Weight must be >= 0.")
    con.execute(
        """
        INSERT INTO rating_property_weights(property_id, weight)
        VALUES (?, ?)
        ON CONFLICT(property_id) DO UPDATE SET weight=excluded.weight
        """,
        [int(property_id), w],
    )


def delete_weight(con, *, property_id: int) -> None:
    con.execute("DELETE FROM rating_property_weights WHERE property_id=?", [int(property_id)])


def upsert_rule(con, *, property_id: int, rule_json: str | dict) -> None:
    if isinstance(rule_json, dict):
        rule_json = json.dumps(rule_json)
    s = str(rule_json).strip()
    if not s:
        raise ValueError("Rule JSON is required.")
    # Validate JSON early to avoid storing garbage.
    json.loads(s)
    con.execute(
        """
        INSERT INTO rating_property_rules(property_id, rule_json)
        VALUES (?, ?)
        ON CONFLICT(property_id) DO UPDATE SET rule_json=excluded.rule_json
        """,
        [int(property_id), s],
    )


def delete_rule(con, *, property_id: int) -> None:
    con.execute("DELETE FROM rating_property_rules WHERE property_id=?", [int(property_id)])


def get_weight(con, *, property_id: int) -> float | None:
    row = con.execute(
        "SELECT weight FROM rating_property_weights WHERE property_id=? LIMIT 1",
        [int(property_id)],
    ).fetchone()
    if row is None:
        return None
    return float(row[0])


def get_rule_json(con, *, property_id: int) -> str | None:
    row = con.execute(
        "SELECT rule_json FROM rating_property_rules WHERE property_id=? LIMIT 1",
        [int(property_id)],
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def fetch_latest_numeric_measurements(
    con,
    *,
    material_ids: list[int],
    property_ids: list[int],
) -> list[tuple[int, int, float]]:
    """
    Returns (material_id, property_id, value_num) for the latest numeric measurement
    per (material_id, property_id) using the policy:
      ORDER BY COALESCE(t.analysis_date, t.request_date) DESC NULLS LAST,
               t.test_id DESC,
               m.measurement_id DESC
    Only considers non-deleted tests and non-null value_num.
    """
    mids = [int(x) for x in material_ids if x is not None]
    pids = [int(x) for x in property_ids if x is not None]
    if not mids or not pids:
        return []

    rows = con.execute(
        """
        WITH ranked AS (
            SELECT
                t.material_id,
                m.property_id,
                m.value_num,
                ROW_NUMBER() OVER (
                    PARTITION BY t.material_id, m.property_id
                    ORDER BY
                        COALESCE(t.analysis_date, t.request_date) DESC NULLS LAST,
                        t.test_id DESC,
                        m.measurement_id DESC
                ) AS rn
            FROM tests t
            JOIN measurements m ON m.test_id = t.test_id
            WHERE
                t.deleted_at IS NULL
                AND t.material_id = ANY(?)
                AND m.property_id = ANY(?)
                AND m.value_num IS NOT NULL
        )
        SELECT material_id, property_id, value_num
        FROM ranked
        WHERE rn = 1
        """,
        [mids, pids],
    ).fetchall()
    return [(int(r[0]), int(r[1]), float(r[2])) for r in rows]


def fetch_avg_numeric_measurements(
    con,
    *,
    material_ids: list[int],
    property_ids: list[int],
) -> list[tuple[int, int, float]]:
    """
    Returns (material_id, property_id, avg_value_num) for numeric measurements.
    Average is computed over all non-deleted tests (all-time) and non-null value_num.
    """
    mids = [int(x) for x in material_ids if x is not None]
    pids = [int(x) for x in property_ids if x is not None]
    if not mids or not pids:
        return []
    rows = con.execute(
        """
        SELECT
            t.material_id,
            m.property_id,
            AVG(m.value_num) AS avg_v
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE
            t.deleted_at IS NULL
            AND t.material_id = ANY(?)
            AND m.property_id = ANY(?)
            AND m.value_num IS NOT NULL
        GROUP BY t.material_id, m.property_id
        """,
        [mids, pids],
    ).fetchall()
    return [(int(r[0]), int(r[1]), float(r[2])) for r in rows if r[2] is not None]
