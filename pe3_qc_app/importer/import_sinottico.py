from __future__ import annotations

from typing import Any

from pe3_qc_app.db.ids import new_id


def import_sinottico(con, wb, progress) -> int:
    if "SINOTTICO" not in wb.sheetnames:
        progress("Sheet 'SINOTTICO' not found. Skipping sinottico.")
        return 0

    ws = wb["SINOTTICO"]
    # expected headers in row 2: MAC / CODICE / DESCRIZIONE / ... / CODICE MATERIALE
    # Items start in row 3. Column A may be blank even on a material row.
    items = []
    seen_materials_by_machine: set[tuple[int, str | None]] = set()
    duplicates = 0
    for r in range(3, ws.max_row + 1):
        label = _cell_str(ws.cell(r, 1).value)
        machine_code = _cell_str(ws.cell(r, 2).value)
        excel_code = _cell_str(ws.cell(r, 3).value)
        desc = _cell_str(ws.cell(r, 4).value)

        # try linking using computed material code (col G) if present in cached values
        material_code = _cell_str(ws.cell(r, 7).value)
        if not (label or excel_code or material_code):
            continue
        material_id = _resolve_material_id(con, material_code, excel_code, desc)
        if not (label or material_id is not None):
            continue
        if material_id is not None:
            key = (material_id, _norm(machine_code) if machine_code else None)
            if key in seen_materials_by_machine:
                duplicates += 1
                continue
            seen_materials_by_machine.add(key)

        items.append([new_id(), machine_code, label, excel_code, desc, material_id, len(items) + 1])

    if not items:
        progress("No importable rows in 'SINOTTICO'. Existing Sinottico rows were kept.")
        return 0

    con.execute("DELETE FROM sinottico_items")
    con.executemany(
        """
        INSERT INTO sinottico_items(item_id, machine_code, excel_label, excel_code, description, material_id, sort_order, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, TRUE)
        """,
        items,
    )
    progress(f"Sinottico items inserted: {len(items)}")
    if duplicates:
        progress(f"Duplicate Sinottico material rows skipped: {duplicates}")
    return len(items)


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
