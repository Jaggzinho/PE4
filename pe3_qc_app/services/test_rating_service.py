from __future__ import annotations

import json
import math
from dataclasses import dataclass

from pe3_qc_app.db.repos.rating_repo import fetch_avg_numeric_measurements, list_rules, list_weights


EPSILON_AVG = 1e-12


@dataclass(frozen=True)
class _BandRule:
    max_pct: float | None
    points: float


@dataclass(frozen=True)
class ParsedPctFromAvgBandsRule:
    bands: list[_BandRule]
    max_points: float


def _parse_rule(rule_json: str) -> ParsedPctFromAvgBandsRule:
    data = json.loads(rule_json)
    if not isinstance(data, dict):
        raise ValueError("Rule must be a JSON object.")

    rtype = data.get("type")
    if rtype == "ranges_v1":
        data = {
            "type": "pct_from_avg_bands_v1",
            "max_points": 100,
            "bands": [
                {"max_pct": r.get("max", None), "points": r.get("score", None)}
                for r in (data.get("ranges") or [])
                if isinstance(r, dict)
            ],
        }
        rtype = "pct_from_avg_bands_v1"

    if rtype == "pct_from_avg_v1":
        data = {
            "type": "pct_from_avg_bands_v1",
            "max_points": data.get("max_points", 20),
            "bands": [
                {"max_pct": r.get("max", None), "points": r.get("points", None)}
                for r in (data.get("ranges") or [])
                if isinstance(r, dict)
            ],
        }
        rtype = "pct_from_avg_bands_v1"

    if rtype != "pct_from_avg_bands_v1":
        raise ValueError("Unsupported rule type.")

    bands = data.get("bands")
    if not isinstance(bands, list) or not bands:
        raise ValueError("Rule bands must be a non-empty list.")

    max_points = data.get("max_points", None)
    if max_points is None:
        raise ValueError("max_points is required.")
    max_points_f = float(max_points)
    if max_points_f <= 0:
        raise ValueError("max_points must be > 0.")

    parsed: list[_BandRule] = []
    for b in bands:
        if not isinstance(b, dict):
            raise ValueError("Band must be an object.")
        max_pct = b.get("max_pct", None)
        if max_pct is not None:
            max_pct = float(max_pct)
            if max_pct < 0:
                raise ValueError("Band max_pct must be >= 0.")
        pts = b.get("points", None)
        if pts is None:
            raise ValueError("Band points is required.")
        pts_f = float(pts)
        if pts_f < 0 or pts_f > max_points_f:
            raise ValueError("Band points must be 0..max_points.")
        parsed.append(_BandRule(max_pct=max_pct, points=pts_f))

    finite = [b for b in parsed if b.max_pct is not None]
    nulls = [b for b in parsed if b.max_pct is None]
    if len(nulls) > 1:
        raise ValueError("Only one catch-all band (max_pct=null) is allowed.")
    finite_sorted = sorted(finite, key=lambda x: float(x.max_pct))
    for i in range(1, len(finite_sorted)):
        if float(finite_sorted[i].max_pct) == float(finite_sorted[i - 1].max_pct):
            raise ValueError("Duplicate band max_pct.")

    return ParsedPctFromAvgBandsRule(
        bands=[*finite_sorted, *nulls],
        max_points=max_points_f,
    )


def _points_for_pct_dist(rule: ParsedPctFromAvgBandsRule, pct_dist: float) -> float | None:
    v = float(pct_dist)
    for b in rule.bands:
        if b.max_pct is None or v <= float(b.max_pct):
            return float(b.points)
    return None


def compute_test_ratings(
    con,
    *,
    tests: list[tuple[int, int]],
) -> dict[int, float]:
    """
    Computes rating% for each (test_id, material_id) in tests and returns a mapping
    test_id -> rating_percent. Tests with no scorable contributing properties are omitted.
    """
    pairs = [(int(tid), int(mid)) for tid, mid in (tests or []) if tid is not None and mid is not None]
    if not pairs:
        return {}

    test_ids = sorted({tid for tid, _mid in pairs})
    material_ids = sorted({mid for _tid, mid in pairs})

    weights = {w.property_id: float(w.weight) for w in list_weights(con) if float(w.weight) > 0}
    rules = {r.property_id: r.rule_json for r in list_rules(con)}
    prop_ids = sorted(set(weights.keys()) & set(rules.keys()))
    if not prop_ids:
        return {}

    parsed_rules: dict[int, ParsedPctFromAvgBandsRule] = {}
    for pid in prop_ids:
        try:
            parsed_rules[int(pid)] = _parse_rule(rules[int(pid)])
        except Exception:
            continue
    prop_ids = sorted(set(prop_ids) & set(parsed_rules.keys()))
    if not prop_ids:
        return {}

    avgs = fetch_avg_numeric_measurements(con, material_ids=material_ids, property_ids=prop_ids)
    avg_map: dict[tuple[int, int], float] = {(int(mid), int(pid)): float(a) for mid, pid, a in avgs if a is not None}
    if not avg_map:
        return {}

    rows = con.execute(
        """
        SELECT
            t.test_id,
            t.material_id,
            m.property_id,
            COALESCE(
                m.value_num,
                TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
            ) AS value_num
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE
            t.deleted_at IS NULL
            AND t.test_id = ANY(?)
            AND m.property_id = ANY(?)
        ORDER BY t.test_id, m.measurement_id
        """,
        [test_ids, prop_ids],
    ).fetchall()

    by_test: dict[int, tuple[int, list[tuple[int, float]]]] = {}
    for test_id, material_id, prop_id, value_num in rows:
        if test_id is None or material_id is None or prop_id is None or value_num is None:
            continue
        tid = int(test_id)
        mid = int(material_id)
        item = by_test.get(tid)
        if item is None:
            by_test[tid] = (mid, [(int(prop_id), float(value_num))])
        else:
            m0, items = item
            items.append((int(prop_id), float(value_num)))
            by_test[tid] = (m0, items)

    out: dict[int, float] = {}
    for tid, (mid, items) in by_test.items():
        num = 0.0
        den = 0.0
        for pid, val in items:
            w = float(weights.get(int(pid), 0.0))
            if w <= 0:
                continue
            rule = parsed_rules.get(int(pid))
            if rule is None:
                continue
            avg = avg_map.get((int(mid), int(pid)))
            if avg is None:
                continue
            favg = float(avg)
            if not math.isfinite(favg) or abs(favg) < EPSILON_AVG:
                continue
            fval = float(val)
            if not math.isfinite(fval):
                continue

            pct_dist = abs(fval - favg) / abs(favg) * 100.0
            pts = _points_for_pct_dist(rule, pct_dist)
            if pts is None:
                continue
            score_percent = float(pts) / float(rule.max_points) * 100.0
            num += w * float(score_percent)
            den += w

        if den > 0:
            out[int(tid)] = num / den

    return out

