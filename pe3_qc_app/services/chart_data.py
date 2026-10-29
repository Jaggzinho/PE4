from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
import re
import unicodedata


@dataclass(frozen=True)
class SeriesPoint:
    x: date
    y: float


def list_active_materials(con) -> list[tuple[int, str]]:
    rows = con.execute(
        "SELECT material_id, code, description FROM materials WHERE active ORDER BY code"
    ).fetchall()
    out: list[tuple[int, str]] = []
    for mid, code, desc in rows:
        label = str(code)
        if desc and str(desc).strip():
            label = f"{code} — {str(desc).strip()}"
        out.append((int(mid), label))
    return out


def list_active_properties_full(con) -> list[tuple[int, str, str | None]]:
    rows = con.execute(
        "SELECT property_id, name, unit FROM properties WHERE active ORDER BY COALESCE(sort_order, 9999), name"
    ).fetchall()
    out: list[tuple[int, str, str | None]] = []
    for pid, name, unit in rows:
        u = str(unit).strip() if unit is not None and str(unit).strip() else None
        out.append((int(pid), str(name), u))
    return out


def list_fixed_chart_properties(con) -> list[tuple[int | None, str, str]]:
    """
    Returns the fixed set of 6 chart properties in the required order.

    Each row is: (property_id | None, display_name, unit)
    """
    rows = con.execute("SELECT property_id, name FROM properties").fetchall()
    by_norm: dict[str, int] = {}
    for pid, name in rows:
        if name is None:
            continue
        by_norm[_norm(str(name))] = int(pid)

    fixed: list[tuple[str, str, tuple[str, ...]]] = [
        (
            "Lacerazione B",
            "N/mm",
            (
                "Lacerazione B",
                "Lacerazione b",
                "Lacerazione B_a",
                "Lacerazione BA",
            ),
        ),
        (
            "Lacerazione C",
            "N/mm",
            (
                "Lacerazione C",
                "Lacerazione c",
                "Lacerazione C_a",
                "Lacerazione CA",
            ),
        ),
        ("Abrasione", "mg", ("Abrasione",)),
        ("Durezza", "ShA", ("Durezza",)),
        ("Carico di rottura", "MPa", ("Carico di rottura",)),
        ("Allungamento", "%", ("Allungamento",)),
    ]

    out: list[tuple[int | None, str, str]] = []
    for display_name, unit, aliases in fixed:
        pid: int | None = None
        for alias in (display_name, *aliases):
            pid = by_norm.get(_norm(alias))
            if pid is not None:
                break
        out.append((pid, display_name, unit))
    return out


def list_top_properties_for_material(con, *, material_id: int, limit: int = 6) -> list[tuple[int, str, str | None]]:
    rows = con.execute(
        """
        SELECT
            p.property_id,
            p.name,
            p.unit,
            COUNT(*) AS n
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        JOIN properties p ON p.property_id = m.property_id
        WHERE t.material_id = ? AND t.deleted_at IS NULL AND p.active
        GROUP BY p.property_id, p.name, p.unit
        ORDER BY n DESC, p.name
        LIMIT ?
        """,
        [int(material_id), int(limit)],
    ).fetchall()
    out: list[tuple[int, str, str | None]] = []
    for pid, name, unit, _n in rows:
        u = str(unit).strip() if unit is not None and str(unit).strip() else None
        out.append((int(pid), str(name), u))
    return out


def _norm(s: str) -> str:
    s2 = " ".join(s.strip().lower().split())
    s2 = unicodedata.normalize("NFKD", s2)
    return "".join(ch for ch in s2 if not unicodedata.combining(ch))


def fetch_date_bounds(con, *, material_id: int) -> tuple[date | None, date | None]:
    row = con.execute(
        """
        SELECT
          MIN(prod_date) AS dmin,
          MAX(prod_date) AS dmax
        FROM tests
        WHERE material_id = ? AND deleted_at IS NULL
          AND prod_date IS NOT NULL
          AND prod_date <> DATE '1900-01-01'
        """,
        [material_id],
    ).fetchone()
    if not row:
        return (None, None)
    dmin, dmax = row
    if dmin is None or dmax is None:
        return (None, None)
    if isinstance(dmin, datetime):
        dmin = dmin.date()
    if isinstance(dmax, datetime):
        dmax = dmax.date()
    return (dmin, dmax)


def fetch_series(
    con,
    *,
    material_id: int,
    property_id: int,
    date_from: date | None,
    date_to: date | None,
) -> list[SeriesPoint]:
    where = [
        "t.material_id = ?",
        "t.deleted_at IS NULL",
        "t.prod_date IS NOT NULL",
        "t.prod_date <> DATE '1900-01-01'",
        "m.property_id = ?",
    ]
    params: list[object] = [material_id, property_id]
    if date_from:
        where.append("t.prod_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.prod_date <= ?")
        params.append(date_to)

    rows = con.execute(
        f"""
        SELECT t.prod_date AS d, COALESCE(m.value_num,
            TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
        ) AS v
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE {' AND '.join(where)}
        ORDER BY d
        """,
        params,
    ).fetchall()

    out: list[SeriesPoint] = []
    for d, v in rows:
        if d is None or v is None:
            continue
        out.append(SeriesPoint(x=d, y=float(v)))
    return out


def fetch_avg(con, *, material_id: int, property_id: int, date_from: date | None, date_to: date | None) -> float | None:
    where = [
        "t.material_id = ?",
        "t.deleted_at IS NULL",
        "t.prod_date IS NOT NULL",
        "t.prod_date <> DATE '1900-01-01'",
        "m.property_id = ?",
    ]
    params: list[object] = [material_id, property_id]
    if date_from:
        where.append("t.prod_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.prod_date <= ?")
        params.append(date_to)

    row = con.execute(
        f"""
        SELECT AVG(COALESCE(m.value_num,
            TRY_CAST(REPLACE(REPLACE(REPLACE(m.value_text, '%', ''), ' ', ''), ',', '.') AS DOUBLE)
        )) AS avg
        FROM tests t
        JOIN measurements m ON m.test_id = t.test_id
        WHERE {' AND '.join(where)}
        """,
        params,
    ).fetchone()
    if not row:
        return None
    return row[0]


def fetch_tolerance(con, *, property_id: int, material_id: int, custom_only: bool = False) -> dict | None:
    custom_filter = "AND is_custom IS TRUE" if custom_only else ""
    row = con.execute(
        f"""
        SELECT warn_low, warn_high, alarm_low, alarm_high, reference_value
        FROM tolerances
        WHERE property_id=? AND (material_id=? OR material_id IS NULL) {custom_filter}
        ORDER BY COALESCE(is_custom, FALSE) DESC, material_id IS NOT NULL DESC,
                 updated_at DESC, tolerance_id DESC
        LIMIT 1
        """,
        [property_id, material_id],
    ).fetchone()
    if not row:
        return None
    return {"warn_low": row[0], "warn_high": row[1], "alarm_low": row[2], "alarm_high": row[3], "reference_value": row[4]}


def fetch_tolerance_exact(con, *, property_id: int, material_id: int) -> dict | None:
    row = con.execute(
        """
        SELECT warn_low, warn_high, alarm_low, alarm_high, reference_value
        FROM tolerances
        WHERE property_id=? AND material_id=?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        [property_id, material_id],
    ).fetchone()
    if not row:
        return None
    return {"warn_low": row[0], "warn_high": row[1], "alarm_low": row[2], "alarm_high": row[3], "reference_value": row[4]}


def durezza_tol_from_material_description(desc: str | None) -> dict | None:
    """
    Detect hardness class (70/80/90) in the material description and return
    a fixed alarm band of +/- 2 (absolute, not percent).

    Rules:
    - Standalone numbers only (e.g. "80", not "180" or "801")
    - Ignore percent forms (e.g. "80%" or "80 %")
    - If multiple are present, priority is 90 > 80 > 70
    """
    if desc is None:
        return None
    s = str(desc)
    if not s.strip():
        return None

    hits: set[int] = set()
    for m in re.finditer(r"(?<!\d)(70|80|90)(?!\d)", s):
        end = m.end()
        j = end
        while j < len(s) and s[j].isspace():
            j += 1
        if j < len(s) and s[j] == "%":
            continue
        hits.add(int(m.group(1)))

    if not hits:
        return None

    base = max(hits)
    return {"warn_low": None, "warn_high": None, "alarm_low": float(base - 2), "alarm_high": float(base + 2)}


def baseline_from_tolerance(tol: dict | None, fallback_avg: float | None) -> float | None:
    if tol is None:
        return fallback_avg

    def _finite(v) -> float | None:
        if v is None:
            return None
        try:
            fv = float(v)
        except Exception:
            return None
        if not math.isfinite(fv):
            return None
        return fv

    al = _finite(tol.get("alarm_low"))
    ah = _finite(tol.get("alarm_high"))
    if al is not None and ah is not None:
        return (al + ah) / 2.0

    wl = _finite(tol.get("warn_low"))
    wh = _finite(tol.get("warn_high"))
    if wl is not None and wh is not None:
        return (wl + wh) / 2.0

    return fallback_avg


def tolerance_from_avg_percent(
    avg: float | None,
    *,
    warn_pct: float | None,
    alarm_pct: float | None,
) -> dict | None:
    if avg is None:
        return None
    if warn_pct is None and alarm_pct is None:
        return None
    try:
        favg = float(avg)
    except Exception:
        return None
    if not math.isfinite(favg):
        return None

    base = abs(favg)
    out: dict[str, float | None] = {"warn_low": None, "warn_high": None, "alarm_low": None, "alarm_high": None}

    if warn_pct is not None:
        try:
            fw = float(warn_pct)
        except Exception:
            fw = float("nan")
        if math.isfinite(fw):
            d = base * (fw / 100.0)
            out["warn_low"] = favg - d
            out["warn_high"] = favg + d

    if alarm_pct is not None:
        try:
            fa = float(alarm_pct)
        except Exception:
            fa = float("nan")
        if math.isfinite(fa):
            d = base * (fa / 100.0)
            out["alarm_low"] = favg - d
            out["alarm_high"] = favg + d

    if all(v is None for v in out.values()):
        return None
    return out


def tolerance_from_avg_abs(
    avg: float | None,
    *,
    alarm_delta: float,
) -> dict | None:
    if avg is None:
        return None
    try:
        favg = float(avg)
        fdelta = float(alarm_delta)
    except Exception:
        return None
    if not math.isfinite(favg) or not math.isfinite(fdelta):
        return None
    if fdelta < 0:
        fdelta = abs(fdelta)

    return {"warn_low": None, "warn_high": None, "alarm_low": favg - fdelta, "alarm_high": favg + fdelta}


def date_range_overlaps_bounds(
    date_from: date | None,
    date_to: date | None,
    *,
    dmin: date | None,
    dmax: date | None,
) -> bool:
    if dmin is None or dmax is None:
        return False
    effective_from = date_from or date.min
    effective_to = date_to or date.max
    return not (effective_to < dmin or effective_from > dmax)
