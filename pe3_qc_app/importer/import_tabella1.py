from __future__ import annotations

import hashlib
from typing import Any

import openpyxl

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.importer.xlsm_utils import norm_header
from pe3_qc_app.services.parse import parse_date, parse_float


def import_tabella1(con, wb, progress) -> tuple[int, int, int]:
    if "LOTTI_RISULTATI ANALISI" not in wb.sheetnames:
        progress("Sheet 'LOTTI_RISULTATI ANALISI' not found. Skipping tests.")
        return (0, 0, 0)

    ws = wb["LOTTI_RISULTATI ANALISI"]
    if "Tabella1" not in ws.tables:
        progress("Table 'Tabella1' not found in LOTTI_RISULTATI ANALISI. Skipping.")
        return (0, 0, 0)

    tbl = ws.tables["Tabella1"]
    ref = getattr(tbl, "ref", None) or ws.tables["Tabella1"]
    min_col, min_row, max_col, max_row = openpyxl.utils.range_boundaries(ref)

    headers = [ws.cell(min_row, c).value for c in range(min_col, max_col + 1)]
    headers_n = [norm_header(h) for h in headers]

    def find_col(name: str) -> int | None:
        try:
            i = headers_n.index(norm_header(name))
        except ValueError:
            return None
        return min_col + i

    c_req = find_col("Data Richiesta")
    c_mat = find_col("Codice Materiale")
    c_mat_desc = find_col("Descrizione Materiale")
    c_lastrina = find_col("Codice Lastrina")
    c_prod = find_col("Data Prod Effettiva")
    c_analysis_date = find_col("DATA ANALISI")

    # Composition columns (3 per type)
    comp_cols: dict[str, tuple[int | None, int | None, int | None]] = {}
    for t in ("ISO", "POL", "CAT", "ADD1", "ADD2"):
        comp_cols[t] = (
            find_col(f"CODICE {t}"),
            find_col(f"DESCRIZIONE {t}"),
            find_col(f"LOTTO {t}"),
        )

    if not c_mat:
        progress("Missing 'Codice Materiale' in Tabella1 headers. Aborting Tabella1 import.")
        return (0, 0, 0)

    prop_cols: list[tuple[int, str]] = []
    props_created = 0
    if c_analysis_date:
        start_idx = (c_analysis_date - min_col) + 1
        for col_idx, name in enumerate(headers[start_idx:], start=min_col + start_idx):
            if not name:
                continue
            prop_name = str(name).strip()
            if not prop_name or prop_name.lower().startswith("coll"):
                continue
            if _ensure_property(con, prop_name):
                props_created += 1
            prop_cols.append((col_idx, prop_name))
    else:
        for c, h in zip(range(min_col, max_col + 1), headers, strict=False):
            if not h:
                continue
            hn = str(h).strip().lower()
            if hn in {"durezza", "carico di rottura", "allungamento", "abrasione"} or "lacerazione" in hn:
                prop_name = str(h).strip()
                if _ensure_property(con, prop_name):
                    props_created += 1
                prop_cols.append((c, prop_name))

    prop_id_by_name = {str(r[0]): int(r[1]) for r in con.execute("SELECT name, property_id FROM properties").fetchall()}

    tests = 0
    meas = 0
    from pe3_qc_app.services.time_utils import utc_now_naive

    now = utc_now_naive()

    progress("Importing Tabella1 rows...")
    for r in range(min_row + 1, max_row + 1):
        mat_code_v = ws.cell(r, c_mat).value
        if not mat_code_v:
            continue
        mat_code = str(mat_code_v).strip()
        if not mat_code:
            continue

        req_date = parse_date(ws.cell(r, c_req).value) if c_req else None
        prod_date = parse_date(ws.cell(r, c_prod).value) if c_prod else None
        analysis_date = parse_date(ws.cell(r, c_analysis_date).value) if c_analysis_date else None
        lastrina_code = _cell_str(ws.cell(r, c_lastrina).value) if c_lastrina else None
        mat_desc = _cell_str(ws.cell(r, c_mat_desc).value) if c_mat_desc else None

        material_row = con.execute(
            "SELECT material_id, description, lastrina_code FROM materials WHERE code = ?",
            [mat_code],
        ).fetchone()
        if material_row is None:
            material_id = new_id()
            con.execute(
                """
                INSERT INTO materials(material_id, code, description, active)
                VALUES (?, ?, ?, TRUE)
                """,
                [material_id, mat_code, mat_desc],
            )
            material_row = (material_id, mat_desc, None)
        material_id = int(material_row[0])
        if material_row[1] is None and mat_desc is not None:
            con.execute("UPDATE materials SET description = ? WHERE material_id = ?", [mat_desc, material_id])
        if lastrina_code:
            if material_row[2] is None:
                con.execute(
                    "UPDATE materials SET lastrina_code = ? WHERE material_id = ?",
                    [lastrina_code, material_id],
                )

        key_src = f"{mat_code}|{req_date}|{prod_date}|{analysis_date}|{lastrina_code}"
        row_key = hashlib.sha1(key_src.encode("utf-8")).hexdigest()

        existing_test = con.execute(
            "SELECT test_id FROM tests WHERE external_source='Tabella1' AND external_row_key=?",
            [row_key],
        ).fetchone()
        preexisting = existing_test is not None
        if existing_test is None:
            test_id = new_id()
            con.execute(
                """
                INSERT INTO tests(
                    test_id, material_id, request_date, prod_date, analysis_date,
                    notes, created_by, created_at, deleted_at, external_source, external_row_key
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL, 'Tabella1', ?)
                """,
                [test_id, material_id, req_date, prod_date, analysis_date, now, row_key],
            )
            tests += 1
        else:
            test_id = int(existing_test[0])

        if preexisting:
            con.execute("DELETE FROM measurements WHERE test_id = ?", [test_id])
            con.execute("DELETE FROM test_component_lots WHERE test_id = ?", [test_id])

        _upsert_component_lots(con, ws, row=r, test_id=int(test_id), comp_cols=comp_cols)

        for col_idx, prop_name in prop_cols:
            prop_id = prop_id_by_name.get(prop_name)
            if not prop_id:
                continue
            val = ws.cell(r, col_idx).value
            num = parse_float(val)
            txt = None if num is not None else _cell_str(val)
            if num is None and txt is None:
                continue
            con.execute(
                """
                INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                [new_id(), test_id, prop_id, num, txt],
            )
            meas += 1

    progress(f"Tabella1 tests imported/updated: {tests}, measurements inserted: {meas}, properties ensured: {props_created}")
    return (tests, meas, props_created)


def _ensure_property(con, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    row = con.execute("SELECT property_id FROM properties WHERE name = ?", [name]).fetchone()
    if row is not None:
        return False
    con.execute(
        """
        INSERT INTO properties(property_id, name, unit, data_type, active, sort_order)
        VALUES (?, ?, NULL, 'num', TRUE, NULL)
        """,
        [new_id(), name],
    )
    return True


def _cell_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _upsert_component_lots(con, ws, *, row: int, test_id: int, comp_cols: dict[str, tuple[int | None, int | None, int | None]]) -> None:
    for type_name, (c_code, c_desc, c_lot) in comp_cols.items():
        code = _cell_str(ws.cell(row, c_code).value) if c_code else None
        desc = _cell_str(ws.cell(row, c_desc).value) if c_desc else None
        lot = _cell_str(ws.cell(row, c_lot).value) if c_lot else None
        if code and not desc:
            try:
                r = con.execute("SELECT description FROM components WHERE code = ? LIMIT 1", [code]).fetchone()
            except Exception:
                r = None
            if r is not None and r[0] is not None and str(r[0]).strip():
                desc = str(r[0]).strip()
        if not (code or desc or lot):
            continue
        con.execute(
            """
            INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(test_id, type_name) DO UPDATE SET
              component_code=excluded.component_code,
              component_desc=excluded.component_desc,
              lot_code=excluded.lot_code
            """,
            [int(test_id), str(type_name), code, desc, lot],
        )
