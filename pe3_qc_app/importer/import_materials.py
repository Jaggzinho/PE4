from __future__ import annotations

from typing import Any

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.importer.xlsm_utils import norm_header


def import_materials(con, wb, progress) -> int:
    if "materiali" not in wb.sheetnames:
        progress("Sheet 'materiali' not found. Skipping materials.")
        return 0

    ws = wb["materiali"]
    headers = [norm_header(ws.cell(1, c).value) for c in range(1, ws.max_column + 1)]
    idx = {h: i + 1 for i, h in enumerate(headers) if h}

    def col(name: str) -> int | None:
        return idx.get(norm_header(name))

    c_code = col("codice mat")
    c_desc = col("desc materiale")
    c_las_code = col("cod lastrina")
    c_las_desc = col("desc last")
    if not c_code:
        progress("Could not find 'codice mat' column in 'materiali'. Skipping materials.")
        return 0

    seen: set[str] = set()
    count = 0
    for r in range(2, ws.max_row + 1):
        code_v = ws.cell(r, c_code).value
        if not code_v:
            continue
        code = str(code_v).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        desc = _cell_str(ws.cell(r, c_desc).value) if c_desc else None
        las_code = _cell_str(ws.cell(r, c_las_code).value) if c_las_code else None
        las_desc = _cell_str(ws.cell(r, c_las_desc).value) if c_las_desc else None

        existing = con.execute(
            "SELECT description, lastrina_code, lastrina_desc FROM materials WHERE code = ?",
            [code],
        ).fetchone()
        if existing is None:
            con.execute(
                """
                INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, TRUE)
                """,
                [new_id(), code, desc, las_code, las_desc],
            )
        else:
            desired = (desc, existing[1] or las_code, existing[2] or las_desc)
            if tuple(existing) != desired:
                con.execute(
                    """
                    UPDATE materials
                    SET description=?, lastrina_code=?, lastrina_desc=?
                    WHERE code=?
                    """,
                    [desired[0], desired[1], desired[2], code],
                )
        count += 1

    progress(f"Materials imported/updated: {count}")
    return count


def _cell_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None
