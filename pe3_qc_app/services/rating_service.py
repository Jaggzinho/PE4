from __future__ import annotations

import json
from dataclasses import dataclass
import math
from datetime import date

from pe3_qc_app.db.repos.rating_repo import (
    fetch_avg_numeric_measurements,
    fetch_latest_numeric_measurements,
    list_rules,
    list_weights,
)
from pe3_qc_app.db.repos.tolerances_repo import Tolerance, list_tolerances
from pe3_qc_app.services.chart_data import baseline_from_tolerance


EPSILON_AVG = 1e-12


def _rating_tolerances(con, *, material_ids: list[int], property_ids: list[int]) -> dict[tuple[int | None, int], Tolerance]:
    mids, pids = set(material_ids), set(property_ids)
    selected: dict[tuple[int | None, int], Tolerance] = {}
    # Repository rows are ordered newest first within each material/property pair.
    for row in list_tolerances(con):
        if row.is_custom and row.property_id in pids and (row.material_id is None or row.material_id in mids):
            selected.setdefault((row.material_id, row.property_id), row)
    return selected


def _tolerance_score(value: float, tolerance: Tolerance, fallback_avg: float | None) -> float | None:
    baseline = tolerance.reference_value
    if baseline is None:
        baseline = baseline_from_tolerance({key: getattr(tolerance, key) for key in ("warn_low", "warn_high", "alarm_low", "alarm_high")}, fallback_avg)
    if baseline is None or not math.isfinite(baseline):
        return None
    if value == baseline:
        return 100.0
    side = "low" if value < baseline else "high"
    warn = getattr(tolerance, f"warn_{side}")
    alarm = getattr(tolerance, f"alarm_{side}")
    if warn is None and alarm is None:
        return 100.0
    if alarm is not None:
        if (value <= alarm if side == "low" else value >= alarm):
            return 0.0
        if warn is not None:
            if (value >= warn if side == "low" else value <= warn):
                return 100.0
            start = warn
        else:
            start = baseline
        span = abs(alarm - start)
        return max(0.0, min(100.0, 100.0 * abs(alarm - value) / span)) if span > 0 else 0.0
    return 100.0 if (value >= warn if side == "low" else value <= warn) else 0.0


def _score_measurement(
    *, material_id: int, property_id: int, value: float, avg: float | None,
    rules: dict[int, "ParsedPctFromAvgBandsRule"], tolerances: dict[tuple[int | None, int], Tolerance],
) -> float | None:
    if not math.isfinite(value):
        return None
    tolerance = tolerances.get((material_id, property_id)) or tolerances.get((None, property_id))
    if tolerance is not None:
        score = _tolerance_score(value, tolerance, avg)
        if score is not None:
            return score
        if tolerance.reference_value is not None:
            avg = tolerance.reference_value
    rule = rules.get(property_id)
    if rule is None or avg is None or not math.isfinite(avg) or abs(avg) < EPSILON_AVG:
        return None
    points = _points_for_pct_dist(rule, abs(value - avg) / abs(avg) * 100.0)
    return None if points is None else float(points) / float(rule.max_points) * 100.0


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
        # Backward-compat: treat old numeric "score" rules as percent-distance points with max_points=100.
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
        # Backward-compat: convert ranges -> bands by taking the max bound as the tolerance threshold.
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


def score_value(rule_json: str, value_num: float) -> float | None:
    """
    Backward-compatible helper: scores a raw value against the rule's ranges directly.
    This remains for validation/tests; rating computation uses pct distance from avg.
    """
    rule = _parse_rule(rule_json)
    v = float(value_num)
    for b in rule.bands:
        if b.max_pct is None or v <= float(b.max_pct):
            return float(b.points)
    return None


def validate_rule_json(rule_json: str) -> None:
    """
    Raises ValueError if the rule JSON is invalid or unsupported.
    """
    _parse_rule(rule_json)


def compute_material_rating(con, *, material_id: int) -> float | None:
    res = compute_ratings_for_materials(con, material_ids=[int(material_id)])
    return res.get(int(material_id))


def compute_ratings_for_materials(con, *, material_ids: list[int]) -> dict[int, float]:
    """
    Returns a mapping material_id -> rating_percent for materials that have at least one
    contributing property. Materials with no contributing properties are omitted.
    """
    mids = [int(x) for x in material_ids if x is not None]
    if not mids:
        return {}

    weights = {w.property_id: float(w.weight) for w in list_weights(con) if float(w.weight) > 0}
    rules = {r.property_id: r.rule_json for r in list_rules(con)}

    prop_ids = sorted(weights.keys())
    if not prop_ids:
        return {}

    parsed_rules: dict[int, ParsedPctFromAvgBandsRule] = {}
    for pid in prop_ids:
        try:
            parsed_rules[pid] = _parse_rule(rules[pid])
        except Exception:
            continue

    tolerances = _rating_tolerances(con, material_ids=mids, property_ids=prop_ids)
    prop_ids = [pid for pid in prop_ids if pid in parsed_rules or any(key[1] == pid for key in tolerances)]
    if not prop_ids:
        return {}

    latest = fetch_latest_numeric_measurements(con, material_ids=mids, property_ids=prop_ids)
    avgs = fetch_avg_numeric_measurements(con, material_ids=mids, property_ids=prop_ids)
    avg_map: dict[tuple[int, int], float] = {(int(mid), int(pid)): float(a) for mid, pid, a in avgs}

    by_mat: dict[int, list[tuple[int, float]]] = {}
    for mid, pid, val in latest:
        by_mat.setdefault(int(mid), []).append((int(pid), float(val)))

    out: dict[int, float] = {}
    for mid, items in by_mat.items():
        num = 0.0
        den = 0.0
        for pid, val in items:
            w = float(weights.get(pid, 0.0))
            if w <= 0:
                continue
            avg = avg_map.get((int(mid), int(pid)))
            score_percent = _score_measurement(material_id=int(mid), property_id=int(pid), value=float(val), avg=avg, rules=parsed_rules, tolerances=tolerances)
            if score_percent is None:
                continue

            num += w * float(score_percent)
            den += w
        if den > 0:
            out[int(mid)] = num / den
    return out


def _points_for_pct_dist(rule: ParsedPctFromAvgBandsRule, pct_dist: float) -> float | None:
    v = float(pct_dist)
    for b in rule.bands:
        if b.max_pct is None or v <= float(b.max_pct):
            return float(b.points)
    return None


def fetch_rating_series(
    con,
    *,
    material_id: int,
    date_from: date | None,
    date_to: date | None,
) -> list[tuple[date, float]]:
    """
    Returns a time series of (prod_date, rating_percent) for each test in the
    requested date window for the given material.

    Rating for each test uses saved material/property tolerances where available,
    and the existing percentage-from-average rule otherwise.

    - Uses tests.prod_date as the x-axis.
    - Skips tests that have no scorable contributing properties.
    """
    mid = int(material_id)
    weights = {w.property_id: float(w.weight) for w in list_weights(con) if float(w.weight) > 0}
    rules = {r.property_id: r.rule_json for r in list_rules(con)}
    prop_ids = sorted(weights.keys())
    if not prop_ids:
        return []

    parsed_rules: dict[int, ParsedPctFromAvgBandsRule] = {}
    for pid in prop_ids:
        try:
            parsed_rules[int(pid)] = _parse_rule(rules[int(pid)])
        except Exception:
            continue
    tolerances = _rating_tolerances(con, material_ids=[mid], property_ids=prop_ids)
    prop_ids = [pid for pid in prop_ids if pid in parsed_rules or any(key[1] == pid for key in tolerances)]
    if not prop_ids:
        return []

    # All-time averages for baseline.
    avgs = fetch_avg_numeric_measurements(con, material_ids=[mid], property_ids=prop_ids)
    avg_map: dict[int, float] = {int(pid): float(a) for _mid, pid, a in avgs if int(_mid) == mid and a is not None}
    if not avg_map and not tolerances:
        return []

    where = [
        "t.deleted_at IS NULL",
        "t.material_id = ?",
        "t.prod_date IS NOT NULL",
        "t.prod_date <> DATE '1900-01-01'",
        "m.property_id = ANY(?)",
    ]
    params: list[object] = [mid, prop_ids]
    if date_from is not None:
        where.append("t.prod_date >= ?")
        params.append(date_from)
    if date_to is not None:
        where.append("t.prod_date <= ?")
        params.append(date_to)

    rows = con.execute(
        f"""
        SELECT
            t.test_id,
            t.prod_date,
            m.property_id,
            COALESCE(
                m.value_num,
                TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
            ) AS value_num
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE {' AND '.join(where)}
        ORDER BY t.prod_date, t.test_id, m.measurement_id
        """,
        params,
    ).fetchall()

    by_test: dict[int, tuple[date, list[tuple[int, float]]]] = {}
    for test_id, req_date, pid, value_num in rows:
        if req_date is None or value_num is None:
            continue
        tid = int(test_id)
        item = by_test.get(tid)
        if item is None:
            by_test[tid] = (req_date, [(int(pid), float(value_num))])
        else:
            d, items = item
            items.append((int(pid), float(value_num)))
            by_test[tid] = (d, items)

    out: list[tuple[date, float]] = []
    for _tid, (d, items) in sorted(by_test.items(), key=lambda kv: (kv[1][0], kv[0])):
        num = 0.0
        den = 0.0
        for pid, val in items:
            w = float(weights.get(int(pid), 0.0))
            if w <= 0:
                continue
            avg = avg_map.get(int(pid))
            score_percent = _score_measurement(material_id=mid, property_id=int(pid), value=float(val), avg=avg, rules=parsed_rules, tolerances=tolerances)
            if score_percent is None:
                continue

            num += w * float(score_percent)
            den += w
        if den > 0:
            out.append((d, num / den))

    return out


def has_rating_configuration(con, *, material_id: int | None = None) -> bool:
    """
    Returns True when there is at least one property with a positive weight and a
    valid parseable rule.
    """
    weights = {w.property_id: float(w.weight) for w in list_weights(con) if float(w.weight) > 0}
    rules = {r.property_id: r.rule_json for r in list_rules(con)}
    prop_ids = sorted(weights.keys())
    if not prop_ids:
        return False
    for pid in prop_ids:
        try:
            _parse_rule(rules[int(pid)])
            return True
        except Exception:
            continue
    for tolerance in list_tolerances(con):
        if tolerance.is_custom and tolerance.property_id in weights and (material_id is None or tolerance.material_id in (None, material_id)):
            if any(getattr(tolerance, bound) is not None for bound in ("warn_low", "warn_high", "alarm_low", "alarm_high")):
                return True
    return False


def compute_average_ratings_for_materials(con, *, material_ids: list[int]) -> dict[int, float]:
    """
    Returns a mapping material_id -> average_rating_percent (all-time), computed as
    the arithmetic mean of per-test rating% values for each material across all
    non-deleted tests that have a request_date.

    Each test contributes at most one rating point (computed as a weighted mean
    across contributing properties present on that test).
    """
    mids = [int(x) for x in material_ids if x is not None]
    if not mids:
        return {}

    weights = {w.property_id: float(w.weight) for w in list_weights(con) if float(w.weight) > 0}
    rules = {r.property_id: r.rule_json for r in list_rules(con)}
    prop_ids = sorted(weights.keys())
    if not prop_ids:
        return {}

    parsed_rules: dict[int, ParsedPctFromAvgBandsRule] = {}
    for pid in prop_ids:
        try:
            parsed_rules[int(pid)] = _parse_rule(rules[int(pid)])
        except Exception:
            continue
    tolerances = _rating_tolerances(con, material_ids=mids, property_ids=prop_ids)
    prop_ids = [pid for pid in prop_ids if pid in parsed_rules or any(key[1] == pid for key in tolerances)]
    if not prop_ids:
        return {}

    avgs = fetch_avg_numeric_measurements(con, material_ids=mids, property_ids=prop_ids)
    avg_map: dict[tuple[int, int], float] = {(int(mid), int(pid)): float(a) for mid, pid, a in avgs if a is not None}
    if not avg_map and not tolerances:
        return {}

    rows = con.execute(
        """
        SELECT
            t.material_id,
            t.test_id,
            m.property_id,
            COALESCE(
                m.value_num,
                TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
            ) AS value_num
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE
            t.deleted_at IS NULL
            AND t.request_date IS NOT NULL
            AND t.material_id = ANY(?)
            AND m.property_id = ANY(?)
        ORDER BY t.material_id, t.test_id, m.measurement_id
        """,
        [mids, prop_ids],
    ).fetchall()

    by_test: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for mid, test_id, pid, value_num in rows:
        if value_num is None:
            continue
        key = (int(mid), int(test_id))
        by_test.setdefault(key, []).append((int(pid), float(value_num)))

    sums: dict[int, float] = {}
    counts: dict[int, int] = {}

    for (mid, _tid), items in by_test.items():
        num = 0.0
        den = 0.0
        for pid, val in items:
            w = float(weights.get(int(pid), 0.0))
            if w <= 0:
                continue
            avg = avg_map.get((int(mid), int(pid)))
            score_percent = _score_measurement(material_id=int(mid), property_id=int(pid), value=float(val), avg=avg, rules=parsed_rules, tolerances=tolerances)
            if score_percent is None:
                continue

            num += w * float(score_percent)
            den += w

        if den > 0:
            rating_pct = num / den
            sums[int(mid)] = float(sums.get(int(mid), 0.0)) + float(rating_pct)
            counts[int(mid)] = int(counts.get(int(mid), 0)) + 1

    out: dict[int, float] = {}
    for mid in mids:
        c = int(counts.get(int(mid), 0))
        if c <= 0:
            continue
        out[int(mid)] = float(sums[int(mid)]) / float(c)
    return out
