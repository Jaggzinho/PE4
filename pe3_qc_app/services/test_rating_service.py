from __future__ import annotations

from pe3_qc_app.db.repos.rating_repo import fetch_avg_numeric_measurements, list_rules, list_weights


from pe3_qc_app.services.rating_service import (
    ParsedPctFromAvgBandsRule, _property_rule, _rating_tolerances, _score_measurement,
)


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
    prop_ids = sorted(weights.keys())
    if not prop_ids:
        return {}

    parsed_rules: dict[int, ParsedPctFromAvgBandsRule] = {}
    for pid in prop_ids:
        try:
            parsed_rules[int(pid)] = _property_rule(con, int(pid), rules[int(pid)])
        except Exception:
            continue
    tolerances = _rating_tolerances(con, material_ids=material_ids, property_ids=prop_ids)

    avgs = fetch_avg_numeric_measurements(con, material_ids=material_ids, property_ids=prop_ids)
    avg_map: dict[tuple[int, int], float] = {(int(mid), int(pid)): float(a) for mid, pid, a in avgs if a is not None}

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
            score_percent = _score_measurement(
                material_id=mid, property_id=pid, value=val,
                avg=avg_map.get((mid, pid)), rules=parsed_rules, tolerances=tolerances,
            )
            if score_percent is None:
                continue
            num += w * float(score_percent)
            den += w

        if den > 0:
            out[int(tid)] = num / den

    return out

