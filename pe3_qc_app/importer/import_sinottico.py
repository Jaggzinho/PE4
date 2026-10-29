from __future__ import annotations

from typing import Any

from pe3_qc_app.db.ids import new_id


def import_sinottico(con, wb, progress) -> int:
    if "SINOTTICO" not in wb.sheetnames:
        progress("Sheet 'SINOTTICO' not found. Skipping sinottico.")
        return 0

    ws = wb["SINOTTICO"]
    con.execute("DELETE FROM sinottico_items")

    # expected headers in row 2: MAC / CODICE / DESCRIZIONE / ... / CODICE MATERIALE
    # items start from row 3 and are sparse; we iterate a bounded range.
    count = 0
    sort_order = 0
    for r in range(3, ws.max_row + 1):
        label = _cell_str(ws.cell(r, 1).value)
        if not label:
            continue
        sort_order += 1

        machine_code = _cell_str(ws.cell(r, 2).value)
        excel_code = _cell_str(ws.cell(r, 3).value)
        desc = _cell_str(ws.cell(r, 4).value)

        # try linking using computed material code (col G) if present in cached values
        material_code = _cell_str(ws.cell(r, 7).value)
        material_id = _resolve_material_id(con, material_code, excel_code, desc)

        con.execute(
            """
            INSERT INTO sinottico_items(item_id, machine_code, excel_label, excel_code, description, material_id, sort_order, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, TRUE)
            """,
            [new_id(), machine_code, label, excel_code, desc, material_id, sort_order],
        )
        count += 1

    progress(f"Sinottico items inserted: {count}")
    return count


def _resolve_material_id(con, material_code: str | None, excel_code: str | None, desc: str | None) -> int | None:
    for code in (material_code, excel_code):
        if not code:
            continue
        row = con.execute("SELECT material_id FROM materials WHERE code = ?", [code]).fetchone()
        if row is not None:
            return int(row[0])

    if desc:
        d = _norm(desc)
        row = con.execute("SELECT material_id, description FROM materials WHERE description IS NOT NULL").fetchall()
        for mid, mdesc in row:
            if _norm(str(mdesc)) == d:
                return int(mid)
    return None


def _cell_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _norm(s: str) -> str:
    return " ".join(s.lower().split())
