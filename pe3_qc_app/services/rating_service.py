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
from pe3_qc_app.services.rating_rules import TolerancePointsRule


def _rating_tolerances(con, *, material_ids: list[int], property_ids: list[int]) -> dict[tuple[int | None, int], Tolerance]:
    mids, pids = set(material_ids), set(property_ids)
    selected: dict[tuple[int | None, int], Tolerance] = {}
    # Repository rows are ordered newest first within each material/property pair.
    for row in list_tolerances(con):
        if row.is_custom and row.property_id in pids and (row.material_id is None or row.material_id in mids):
            selected.setdefault((row.material_id, row.property_id), row)
    return selected


def _tolerance_score(
    value: float, tolerance: Tolerance, fallback_avg: float | None,
    rule: ParsedPctFromAvgBandsRule | None = None,
) -> float | None:
    max_points = rule.max_points if rule else 20.0
    points = rule.tolerance_points if rule else None
    points = points or {"warn_low": max_points, "warn_high": max_points, "alarm_low": 0.0, "alarm_high": 0.0}
    # Alarm boundaries are inclusive, even when their configured score is nonzero.
    if tolerance.alarm_low is not None and value < tolerance.alarm_low:
        return 0.0
    if tolerance.alarm_high is not None and value > tolerance.alarm_high:
        return 0.0
    # Prefer the outer limit at coincident warn/alarm boundaries.
    for bound in ("alarm_low", "alarm_high", "warn_low", "warn_high"):
        if getattr(tolerance, bound) == value:
            return points[bound] / max_points * 100.0
    baseline = tolerance.reference_value
    if baseline is None:
        if tolerance.warn_low is not None and tolerance.warn_high is not None:
            baseline = tolerance.warn_low / 2 + tolerance.warn_high / 2
        elif tolerance.alarm_low is not None and tolerance.alarm_high is not None:
            baseline = tolerance.alarm_low / 2 + tolerance.alarm_high / 2
        else:
            baseline = fallback_avg
        # Keep the derived center inside one-sided limits, even if the data average drifts.
        if baseline is not None:
            for bound in (tolerance.alarm_low, tolerance.warn_low):
                if bound is not None:
                    baseline = max(baseline, bound)
            for bound in (tolerance.alarm_high, tolerance.warn_high):
                if bound is not None:
                    baseline = min(baseline, bound)
    if baseline is None or not math.isfinite(baseline):
        return None
    if value == baseline:
        return 100.0
    side = "low" if value < baseline else "high"
    warn = getattr(tolerance, f"warn_{side}")
    alarm = getattr(tolerance, f"alarm_{side}")
    if warn is None and alarm is None:
        return 100.0
    anchors = [(baseline, max_points)]
    if warn is not None:
        anchors.append((warn, points[f"warn_{side}"]))
    if alarm is not None:
        anchors.append((alarm, points[f"alarm_{side}"]))
    anchors.sort(key=lambda item: abs(item[0] - baseline))
    distance = abs(value - baseline)
    for (start, start_points), (end, end_points) in zip(anchors, anchors[1:]):
        span = abs(end - baseline) - abs(start - baseline)
        if distance <= abs(end - baseline) and span > 0:
            fraction = (distance - abs(start - baseline)) / span
            return (start_points + fraction * (end_points - start_points)) / max_points * 100.0
    # A missing alarm leaves that side open; keep the last configured score.
    return anchors[-1][1] / max_points * 100.0


def _score_measurement(
    *, material_id: int, property_id: int, value: float, avg: float | None,
    rules: dict[int, "ParsedPctFromAvgBandsRule"], tolerances: dict[tuple[int | None, int], Tolerance],
) -> float | None:
    if not math.isfinite(value):
        return None
    rule = rules.get(property_id)
    tolerance = tolerances.get((material_id, property_id)) or tolerances.get((None, property_id))
    if tolerance is not None:
        # Only saved QC limits determine the custom scoring intervals.
        if any(getattr(tolerance, bound) is not None for bound in ("warn_low", "warn_high", "alarm_low", "alarm_high")):
            score = _tolerance_score(value, tolerance, avg, rule)
            if score is not None:
                return score
    if avg is None or not math.isfinite(avg):
        return None
    radius = abs(avg) * 0.2
    return 100.0 if avg - radius <= value <= avg + radius else 0.0



@dataclass(frozen=True)
class _BandRule:
    max_pct: float | None
    points: float


@dataclass(frozen=True)
class ParsedPctFromAvgBandsRule:
    bands: list[_BandRule]
    max_points: float
    absolute_distance: bool = False
    tolerance_points: dict[str, float] | None = None


def _parse_rule(rule_json: str) -> ParsedPctFromAvgBandsRule:
    data = json.loads(rule_json)
    if not isinstance(data, dict):
        raise ValueError("Rule must be a JSON object.")

    rtype = data.get("type")
    if rtype == "custom_tolerance_points_v1":
        configured = TolerancePointsRule.model_validate(data)
        points = {bound: getattr(configured, f"{bound}_points") for bound in ("warn_low", "warn_high", "alarm_low", "alarm_high")}
        return ParsedPctFromAvgBandsRule(bands=[], max_points=configured.max_points, tolerance_points=points)
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

    if rtype not in ("pct_from_avg_bands_v1", "absolute_from_reference_bands_v1"):
        raise ValueError("Unsupported rule type.")
    bands = data.get("bands")
    if not isinstance(bands, list) or not bands:
        raise ValueError("Rule bands must be a non-empty list.")

    max_points = data.get("max_points", None)
    if max_points is None:
        raise ValueError("max_points is required.")
    max_points_f = float(max_points)
    if not math.isfinite(max_points_f) or max_points_f <= 0:
        raise ValueError("max_points must be > 0.")

    parsed: list[_BandRule] = []
    for b in bands:
        if not isinstance(b, dict):
            raise ValueError("Band must be an object.")
        max_pct = b.get("max_pct", None)
        if max_pct is not None:
            max_pct = float(max_pct)
            if not math.isfinite(max_pct) or max_pct < 0:
                raise ValueError("Band max_pct must be >= 0.")
        pts = b.get("points", None)
        if pts is None:
            raise ValueError("Band points is required.")
        pts_f = float(pts)
        if not math.isfinite(pts_f) or pts_f < 0 or pts_f > max_points_f:
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
        absolute_distance=rtype == "absolute_from_reference_bands_v1",
    )


def _property_rule(con, property_id: int, rule_json: str) -> ParsedPctFromAvgBandsRule:
    return _parse_rule(rule_json)


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
            parsed_rules[pid] = _property_rule(con, pid, rules[pid])
        except Exception:
            continue

    tolerances = _rating_tolerances(con, material_ids=mids, property_ids=prop_ids)

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
    Returns a time series of (request_date, rating_percent) for each test in the
    requested date window for the given material.

    Rating for each test uses saved material/property tolerances where available,
    and the fixed inclusive +/-20% average band otherwise.

    - Uses tests.request_date as the x-axis.
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
            parsed_rules[int(pid)] = _property_rule(con, int(pid), rules[int(pid)])
        except Exception:
            continue
    tolerances = _rating_tolerances(con, material_ids=[mid], property_ids=prop_ids)

    # All-time averages for baseline.
    avgs = fetch_avg_numeric_measurements(con, material_ids=[mid], property_ids=prop_ids)
    avg_map: dict[int, float] = {int(pid): float(a) for _mid, pid, a in avgs if int(_mid) == mid and a is not None}
    if not avg_map and not tolerances:
        return []

    where = [
        "t.deleted_at IS NULL",
        "t.material_id = ?",
        "t.request_date IS NOT NULL",
        "t.request_date <> DATE '1900-01-01'",
        "m.property_id = ANY(?)",
    ]
    params: list[object] = [mid, prop_ids]
    if date_from is not None:
        where.append("t.request_date >= ?")
        params.append(date_from)
    if date_to is not None:
        where.append("t.request_date <= ?")
        params.append(date_to)

    rows = con.execute(
        f"""
        SELECT
            t.test_id,
            t.request_date,
            m.property_id,
            COALESCE(
                m.value_num,
                TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
            ) AS value_num
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE {' AND '.join(where)}
        ORDER BY t.request_date, t.test_id, m.measurement_id
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
    """A positive property weight enables custom-limit or fixed fallback scoring."""
    return any(float(row.weight) > 0 for row in list_weights(con))


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
            parsed_rules[int(pid)] = _property_rule(con, int(pid), rules[int(pid)])
        except Exception:
            continue
    tolerances = _rating_tolerances(con, material_ids=mids, property_ids=prop_ids)

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
