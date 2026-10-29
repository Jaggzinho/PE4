from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import unicodedata

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.services.parse import parse_float
from pe3_qc_app.services.time_utils import utc_now_naive


@dataclass(frozen=True)
class LottiRow:
    test_id: int
    material_id: int
    material_code: str
    material_desc: str | None
    lastrina_code: str | None
    request_date: date | None
    prod_date: date | None
    analysis_date: date | None

    iso_code: str | None
    iso_desc: str | None
    iso_lot: str | None
    pol_code: str | None
    pol_desc: str | None
    pol_lot: str | None
    cat_code: str | None
    cat_desc: str | None
    cat_lot: str | None
    add1_code: str | None
    add1_desc: str | None
    add1_lot: str | None
    add2_code: str | None
    add2_desc: str | None
    add2_lot: str | None

    durezza: str | None
    carico_rottura: str | None
    allungamento: str | None
    lacerazione_ba: str | None
    lacerazione_ca: str | None
    abrasione: str | None
    resistivita_superficiale: str | None


QC_FIELDS: list[tuple[str, str]] = [
    ("durezza", "Durezza"),
    ("carico_rottura", "Carico di rottura"),
    ("allungamento", "Allungamento"),
    ("lacerazione_ba", "Lacerazione B_a"),
    ("lacerazione_ca", "Lacerazione C_a"),
    ("abrasione", "Abrasione"),
    ("resistivita_superficiale", "Resistività Superficiale"),
]


def create_test_for_sample_request(
    con,
    *,
    item_id: int,
    req_id: int,
    request_date: date,
    requested_by: int | None,
) -> int | None:
    row = con.execute("SELECT material_id FROM sinottico_items WHERE item_id = ?", [int(item_id)]).fetchone()
    if row is None or row[0] is None:
        return None
    material_id = int(row[0])
    test_id = new_id()
    con.execute(
        """
        INSERT INTO tests(
            test_id, material_id, request_date, prod_date, analysis_date,
            notes, created_by, created_at, deleted_at, external_source, external_row_key
        )
        VALUES (?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, 'SampleRequest', ?)
        """,
        [int(test_id), int(material_id), request_date, requested_by, utc_now_naive(), str(int(req_id))],
    )
    return int(test_id)


def create_test_manual(
    con,
    *,
    material_id: int,
    request_date: date | None,
    prod_date: date | None,
    analysis_date: date | None,
    created_by: int | None,
) -> int:
    test_id = new_id()
    con.execute(
        """
        INSERT INTO tests(
            test_id, material_id, request_date, prod_date, analysis_date,
            notes, created_by, created_at, deleted_at, external_source, external_row_key
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, NULL, 'Manual', ?)
        """,
        [int(test_id), int(material_id), request_date, prod_date, analysis_date, created_by, utc_now_naive(), str(int(test_id))],
    )
    return int(test_id)


def get_test_details(con, *, test_id: int) -> dict:
    row = con.execute(
        """
        SELECT test_id, material_id, request_date, prod_date, analysis_date
        FROM tests
        WHERE test_id = ?
        """,
        [int(test_id)],
    ).fetchone()
    if row is None:
        raise ValueError("Test not found.")
    comps = con.execute(
        """
        SELECT
            tcl.type_name,
            tcl.component_code,
            COALESCE(tcl.component_desc, c.description) AS component_desc,
            tcl.lot_code
        FROM test_component_lots tcl
        LEFT JOIN components c ON c.code = tcl.component_code
        WHERE tcl.test_id = ?
        """,
        [int(test_id)],
    ).fetchall()
    comp_map: dict[str, dict[str, str | None]] = {}
    for tname, code, desc, lot in comps:
        comp_map[str(tname)] = {"code": _s(code), "desc": _s(desc), "lot": _s(lot)}

    prop_ids = _resolve_qc_property_ids(con)
    qc: dict[str, str | None] = {f: None for f, _l in QC_FIELDS}
    for field, _label in QC_FIELDS:
        pid = prop_ids.get(field)
        if pid is None:
            continue
        vrow = con.execute(
            """
            SELECT COALESCE(CAST(value_num AS VARCHAR), value_text)
            FROM measurements
            WHERE test_id = ? AND property_id = ?
            ORDER BY measurement_id DESC
            LIMIT 1
            """,
            [int(test_id), int(pid)],
        ).fetchone()
        if vrow is not None:
            qc[field] = _s(vrow[0])

    return {
        "test_id": int(row[0]),
        "material_id": int(row[1]),
        "request_date": row[2],
        "prod_date": row[3],
        "analysis_date": row[4],
        "components": comp_map,
        "qc": qc,
    }


def list_lotti_rows(
    con, *, limit: int = 2000, offset: int = 0, include_deleted: bool = False,
    material_id: int | None = None, test_id: int | None = None,
    query: str | None = None, date_field: str = "request_date",
    date_from: date | None = None, date_to: date | None = None,
    status: str = "all", sort_by: str = "latest", sort_dir: str = "desc",
    component_filters: dict[str, str] | None = None,
    qc_field: str | None = None, qc_min: float | None = None, qc_max: float | None = None,
    return_total: bool = False,
    visible_material_ids: set[int] | None = None,
) -> list[LottiRow] | tuple[list[LottiRow], int]:
    where = []
    params: list[int] = []
    if not include_deleted:
        where.append("t.deleted_at IS NULL")
    if visible_material_ids is not None:
        if not visible_material_ids:
            return ([], 0) if return_total else []
        where.append(f"t.material_id IN ({', '.join('?' for _ in visible_material_ids)})")
        params.extend(sorted(visible_material_ids))
    if material_id is not None:
        where.append("t.material_id = ?")
        params.append(int(material_id))
    if test_id is not None:
        where.append("t.test_id = ?")
        params.append(int(test_id))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    prop_ids = _resolve_qc_property_ids(con)
    qc_selects: list[str] = []
    for field, _label in QC_FIELDS:
        pid = prop_ids.get(field)
        if pid is None:
            qc_selects.append(f"NULL AS {field}")
        else:
            qc_selects.append(
                "MAX(CASE WHEN m.property_id = "
                + str(int(pid))
                + " THEN COALESCE(CAST(m.value_num AS VARCHAR), m.value_text) END) AS "
                + field
            )

    outer_where: list[str] = []
    outer_params: list[object] = []
    cleaned_query = (query or "").strip().lower()
    if cleaned_query:
        searchable = [
            "CAST(test_id AS VARCHAR)", "material_code", "material_desc", "lastrina_code",
            "iso_code", "pol_code", "cat_code", "add1_code", "add2_code",
        ]
        outer_where.append(
            "LOWER(" + " || ' ' || ".join(f"COALESCE({column}, '')" for column in searchable) + ") LIKE ?"
        )
        outer_params.append(f"%{cleaned_query}%")

    date_columns = {"request_date", "prod_date", "analysis_date"}
    safe_date_field = date_field if date_field in date_columns else "request_date"
    if date_from is not None:
        outer_where.append(f"{safe_date_field} >= ?")
        outer_params.append(date_from)
    if date_to is not None:
        outer_where.append(f"{safe_date_field} <= ?")
        outer_params.append(date_to)

    if status == "completed":
        outer_where.append("analysis_date IS NOT NULL")
    elif status == "awaiting_production":
        outer_where.append("prod_date IS NULL")
    elif status == "awaiting_analysis":
        outer_where.append("prod_date IS NOT NULL AND analysis_date IS NULL")

    component_columns = {"iso": "iso_code", "pol": "pol_code", "cat": "cat_code", "add1": "add1_code", "add2": "add2_code"}
    for key, value in (component_filters or {}).items():
        cleaned_value = value.strip()
        if key in component_columns and cleaned_value:
            outer_where.append(f"LOWER({component_columns[key]}) = LOWER(?)")
            outer_params.append(cleaned_value)

    numeric_sort_columns = {field for field, _label in QC_FIELDS}
    if qc_field in numeric_sort_columns:
        numeric_expression = f"TRY_CAST(REPLACE({qc_field}, ',', '.') AS DOUBLE)"
        if qc_min is not None:
            outer_where.append(f"{numeric_expression} >= ?")
            outer_params.append(float(qc_min))
        if qc_max is not None:
            outer_where.append(f"{numeric_expression} <= ?")
            outer_params.append(float(qc_max))

    text_sort_columns = {
        "material": "LOWER(material_code)", "lastrina": "LOWER(lastrina_code)",
        "iso": "LOWER(iso_code)", "pol": "LOWER(pol_code)", "cat": "LOWER(cat_code)",
        "add1": "LOWER(add1_code)", "add2": "LOWER(add2_code)",
    }
    if sort_by == "latest":
        sort_expression = "COALESCE(analysis_date, request_date)"
    elif sort_by in date_columns:
        sort_expression = sort_by
    elif sort_by in text_sort_columns:
        sort_expression = text_sort_columns[sort_by]
    elif sort_by in numeric_sort_columns:
        sort_expression = f"TRY_CAST(REPLACE({sort_by}, ',', '.') AS DOUBLE)"
    else:
        sort_expression = "COALESCE(analysis_date, request_date)"
    direction = "ASC" if sort_dir == "asc" else "DESC"
    outer_where_sql = ("WHERE " + " AND ".join(outer_where)) if outer_where else ""

    cte_sql = f"""
        WITH lot_rows AS (
        SELECT
            t.test_id,
            t.material_id,
            mat.code AS material_code,
            mat.description AS material_desc,
            mat.lastrina_code,
            t.request_date,
            t.prod_date,
            t.analysis_date,

            MAX(CASE WHEN tcl.type_name='ISO'  THEN tcl.component_code END) AS iso_code,
            MAX(CASE WHEN tcl.type_name='ISO'  THEN COALESCE(tcl.component_desc, c.description) END) AS iso_desc,
            MAX(CASE WHEN tcl.type_name='ISO'  THEN tcl.lot_code END)       AS iso_lot,
            MAX(CASE WHEN tcl.type_name='POL'  THEN tcl.component_code END) AS pol_code,
            MAX(CASE WHEN tcl.type_name='POL'  THEN COALESCE(tcl.component_desc, c.description) END) AS pol_desc,
            MAX(CASE WHEN tcl.type_name='POL'  THEN tcl.lot_code END)       AS pol_lot,
            MAX(CASE WHEN tcl.type_name='CAT'  THEN tcl.component_code END) AS cat_code,
            MAX(CASE WHEN tcl.type_name='CAT'  THEN COALESCE(tcl.component_desc, c.description) END) AS cat_desc,
            MAX(CASE WHEN tcl.type_name='CAT'  THEN tcl.lot_code END)       AS cat_lot,
            MAX(CASE WHEN tcl.type_name='ADD1' THEN tcl.component_code END) AS add1_code,
            MAX(CASE WHEN tcl.type_name='ADD1' THEN COALESCE(tcl.component_desc, c.description) END) AS add1_desc,
            MAX(CASE WHEN tcl.type_name='ADD1' THEN tcl.lot_code END)       AS add1_lot,
            MAX(CASE WHEN tcl.type_name='ADD2' THEN tcl.component_code END) AS add2_code,
            MAX(CASE WHEN tcl.type_name='ADD2' THEN COALESCE(tcl.component_desc, c.description) END) AS add2_desc,
            MAX(CASE WHEN tcl.type_name='ADD2' THEN tcl.lot_code END)       AS add2_lot,

            {", ".join(qc_selects)}
        FROM tests t
        JOIN materials mat ON mat.material_id = t.material_id
        LEFT JOIN test_component_lots tcl ON tcl.test_id = t.test_id
        LEFT JOIN components c ON c.code = tcl.component_code
        LEFT JOIN measurements m ON m.test_id = t.test_id
        {where_sql}
        GROUP BY
            t.test_id, t.material_id, mat.code, mat.description, mat.lastrina_code,
            t.request_date, t.prod_date, t.analysis_date
        )
    """
    sql = cte_sql + f"""
        SELECT * FROM lot_rows
        {outer_where_sql}
        ORDER BY {sort_expression} {direction} NULLS LAST, test_id DESC
        LIMIT ? OFFSET ?
    """
    rows = con.execute(sql, [*params, *outer_params, int(limit), int(offset)]).fetchall()
    total = 0
    if return_total:
        count_sql = cte_sql + f"SELECT COUNT(*) FROM lot_rows {outer_where_sql}"
        total = int(con.execute(count_sql, [*params, *outer_params]).fetchone()[0])
    out: list[LottiRow] = []
    for r in rows:
        out.append(
            LottiRow(
                test_id=int(r[0]),
                material_id=int(r[1]),
                material_code=str(r[2]),
                material_desc=(str(r[3]) if r[3] is not None else None),
                lastrina_code=(str(r[4]) if r[4] is not None else None),
                request_date=r[5],
                prod_date=r[6],
                analysis_date=r[7],
                iso_code=_s(r[8]),
                iso_desc=_s(r[9]),
                iso_lot=_s(r[10]),
                pol_code=_s(r[11]),
                pol_desc=_s(r[12]),
                pol_lot=_s(r[13]),
                cat_code=_s(r[14]),
                cat_desc=_s(r[15]),
                cat_lot=_s(r[16]),
                add1_code=_s(r[17]),
                add1_desc=_s(r[18]),
                add1_lot=_s(r[19]),
                add2_code=_s(r[20]),
                add2_desc=_s(r[21]),
                add2_lot=_s(r[22]),
                durezza=_s(r[23]),
                carico_rottura=_s(r[24]),
                allungamento=_s(r[25]),
                lacerazione_ba=_s(r[26]),
                lacerazione_ca=_s(r[27]),
                abrasione=_s(r[28]),
                resistivita_superficiale=_s(r[29]),
            )
        )
    return (out, total) if return_total else out


@dataclass(frozen=True)
class LastrineRequestSummaryRow:
    material_code: str
    material_desc: str | None
    lastrina_code: str | None


def list_lastrine_requests_for_date(con, *, day: date) -> list[LastrineRequestSummaryRow]:
    rows = con.execute(
        """
        SELECT mat.code, mat.description, mat.lastrina_code
        FROM tests t
        JOIN materials mat ON mat.material_id = t.material_id
        WHERE t.deleted_at IS NULL AND t.request_date = ?
        GROUP BY mat.code, mat.description, mat.lastrina_code
        ORDER BY mat.code
        """,
        [day],
    ).fetchall()
    out: list[LastrineRequestSummaryRow] = []
    for code, desc, las_code in rows:
        out.append(
            LastrineRequestSummaryRow(
                material_code=str(code),
                material_desc=(str(desc) if desc is not None else None),
                lastrina_code=(str(las_code) if las_code is not None else None),
            )
        )
    return out


def update_test_dates(con, *, test_id: int, request_date: date | None, prod_date: date | None, analysis_date: date | None) -> None:
    con.execute(
        """
        UPDATE tests
        SET request_date=?, prod_date=?, analysis_date=?
        WHERE test_id=?
        """,
        [request_date, prod_date, analysis_date, int(test_id)],
    )


def update_test_material(con, *, test_id: int, material_id: int) -> None:
    con.execute("UPDATE tests SET material_id=? WHERE test_id=?", [int(material_id), int(test_id)])


def soft_delete_test(con, *, test_id: int) -> None:
    con.execute("UPDATE tests SET deleted_at=? WHERE test_id=?", [utc_now_naive(), int(test_id)])


def hard_delete_test(con, *, test_id: int) -> None:
    """
    Deletes a test row and its dependent rows to avoid FK violations.
    Use with care; this is irreversible.
    """
    tid = int(test_id)

    # Fast-path for current schema.
    con.execute("DELETE FROM measurements WHERE test_id = ?", [tid])
    con.execute("DELETE FROM test_component_lots WHERE test_id = ?", [tid])

    # Compatibility sweep: older/alternate schemas may have additional tables
    # referencing tests(test_id). Delete those dependents as well.
    rows = con.execute(
        """
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE table_schema = 'main' AND column_name = 'test_id'
        ORDER BY table_name
        """
    ).fetchall()
    for (table_name,) in rows:
        tname = str(table_name)
        if tname == "tests":
            continue
        if tname in {"measurements", "test_component_lots"}:
            continue
        con.execute(f"DELETE FROM {tname} WHERE test_id = ?", [tid])

    con.execute("DELETE FROM tests WHERE test_id = ?", [tid])


def backfill_test_component_descriptions(con) -> int:
    """
    One-time (idempotent) repair: fills missing component_desc in test_component_lots
    by binding component_code -> components.description.
    """
    con.execute(
        """
        UPDATE test_component_lots tcl
        SET component_desc = c.description
        FROM components c
        WHERE
            tcl.component_code IS NOT NULL
            AND TRIM(CAST(tcl.component_code AS VARCHAR)) <> ''
            AND (tcl.component_desc IS NULL OR TRIM(CAST(tcl.component_desc AS VARCHAR)) = '')
            AND c.code = tcl.component_code
            AND c.description IS NOT NULL
            AND TRIM(CAST(c.description AS VARCHAR)) <> ''
        """
    )
    try:
        row = con.execute("SELECT changes()").fetchone()
        if row is not None:
            return int(row[0])
    except Exception:
        pass
    return 0


def upsert_component_lot(
    con,
    *,
    test_id: int,
    type_name: str,
    component_code: str | None,
    component_desc: str | None,
    lot_code: str | None,
) -> None:
    component_code = _s(component_code)
    component_desc = _s(component_desc)
    lot_code = _s(lot_code)

    if component_code and not component_desc:
        try:
            row = con.execute("SELECT description FROM components WHERE code = ? LIMIT 1", [component_code]).fetchone()
        except Exception:
            row = None
        if row is not None and row[0] is not None and str(row[0]).strip():
            component_desc = str(row[0]).strip()

    if not (component_code or component_desc or lot_code):
        con.execute("DELETE FROM test_component_lots WHERE test_id=? AND type_name=?", [int(test_id), str(type_name)])
        return
    con.execute(
        """
        INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(test_id, type_name) DO UPDATE SET
          component_code=excluded.component_code,
          component_desc=excluded.component_desc,
          lot_code=excluded.lot_code
        """,
        [int(test_id), str(type_name), component_code, component_desc, lot_code],
    )


def upsert_measurement(con, *, test_id: int, property_name: str, value: str | None) -> None:
    pname = property_name.strip()
    if not pname:
        return
    pid = _ensure_property(con, pname)
    con.execute("DELETE FROM measurements WHERE test_id=? AND property_id=?", [int(test_id), int(pid)])
    txt = (value or "").strip()
    if not txt:
        return
    num = parse_float(txt)
    value_num = num
    value_text = None if num is not None else txt
    con.execute(
        """
        INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        [new_id(), int(test_id), int(pid), value_num, value_text],
    )


def _ensure_property(con, name: str) -> int:
    row = con.execute("SELECT property_id FROM properties WHERE name = ?", [name]).fetchone()
    if row is not None:
        return int(row[0])
    pid = new_id()
    con.execute(
        """
        INSERT INTO properties(property_id, name, unit, data_type, active, sort_order)
        VALUES (?, ?, NULL, 'num', TRUE, NULL)
        """,
        [int(pid), str(name)],
    )
    return int(pid)


def _resolve_qc_property_ids(con) -> dict[str, int | None]:
    rows = con.execute("SELECT property_id, name FROM properties").fetchall()
    by_norm: dict[str, int] = {}
    for pid, name in rows:
        if name is None:
            continue
        by_norm[_norm(str(name))] = int(pid)

    out: dict[str, int | None] = {}
    for field, label in QC_FIELDS:
        out[field] = by_norm.get(_norm(label))
    return out


def _norm(s: str) -> str:
    s2 = " ".join(s.strip().lower().split())
    s2 = unicodedata.normalize("NFKD", s2)
    return "".join(ch for ch in s2 if not unicodedata.combining(ch))


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None
