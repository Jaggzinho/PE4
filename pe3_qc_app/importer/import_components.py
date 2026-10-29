from __future__ import annotations

from typing import Any

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.importer.xlsm_utils import norm_header


_TYPE_TO_SLOT_KEY = {
    "isocianato": "ISO",
    "poliolo": "POL",
    "catalizzatore": "CAT",
    "additivo 1": "ADD1",
    "additivo 2": "ADD2",
    "additivo 3": "ADD3",
    "additivo 4": "ADD4",
    "extender": "EXT",
}


def import_components(con, wb, progress) -> tuple[int, int, int]:
    """
    Imports:
      - component_types from 'TIPOLOGIE COMP' and/or from 'materiali'
      - components from 'materiali' (componenti/desc componenti/UM)
      - material_component_defaults (material_id + slot_key) from 'materiali'
    """
    types_touched = 0
    components_touched = 0
    defaults_touched = 0

    discovered_types: set[str] = set()
    if "TIPOLOGIE COMP" in wb.sheetnames:
        ws_t = wb["TIPOLOGIE COMP"]
        for r in range(2, ws_t.max_row + 1):
            name = _cell_str(ws_t.cell(r, 1).value)
            if not name:
                continue
            discovered_types.add(name)

    if "materiali" not in wb.sheetnames:
        progress("Sheet 'materiali' not found. Skipping component import.")
        return (types_touched, components_touched, defaults_touched)

    ws = wb["materiali"]
    headers = [norm_header(ws.cell(1, c).value) for c in range(1, ws.max_column + 1)]
    idx = {h: i + 1 for i, h in enumerate(headers) if h}

    def col(name: str) -> int | None:
        return idx.get(norm_header(name))

    c_mat = col("codice mat")
    c_type = col("tipo comp")
    c_code = col("componenti")
    c_desc = col("desc componenti")
    c_um = col("um")
    if not c_mat:
        progress("Could not find 'codice mat' column in 'materiali'. Skipping component import.")
        return (types_touched, components_touched, defaults_touched)

    last_mat_code: str | None = None
    comp_by_code: dict[str, dict[str, str | None]] = {}
    defaults_by_mat: dict[str, dict[str, str]] = {}
    for r in range(2, ws.max_row + 1):
        mat_code_v = ws.cell(r, c_mat).value
        if mat_code_v is not None and str(mat_code_v).strip():
            last_mat_code = str(mat_code_v).strip()
        if not last_mat_code:
            continue

        type_name = _cell_str(ws.cell(r, c_type).value) if c_type else None
        comp_code = _cell_str(ws.cell(r, c_code).value) if c_code else None
        comp_desc = _cell_str(ws.cell(r, c_desc).value) if c_desc else None
        unit = _cell_str(ws.cell(r, c_um).value) if c_um else None

        if not (type_name or comp_code or comp_desc or unit):
            continue
        if not type_name or not comp_code:
            continue

        discovered_types.add(type_name)

        prev = comp_by_code.get(comp_code) or {}
        comp_by_code[comp_code] = {
            "type_name": type_name,
            "description": comp_desc if comp_desc is not None else prev.get("description"),
            "unit": unit if unit is not None else prev.get("unit"),
        }

        slot_key = _slot_key_for_type(type_name)
        if slot_key:
            defaults_by_mat.setdefault(last_mat_code, {})[slot_key] = comp_code

    for t in sorted(discovered_types):
        if _ensure_component_type(con, t):
            types_touched += 1

    con.execute("DELETE FROM material_component_defaults")

    type_id_by_name = {str(r[0]): int(r[1]) for r in con.execute("SELECT name, type_id FROM component_types").fetchall()}
    for code, meta in comp_by_code.items():
        tname = meta.get("type_name") or ""
        tid = type_id_by_name.get(tname)
        if tid is None:
            continue
        _upsert_component(con, type_id=int(tid), code=code, description=meta.get("description"), unit=meta.get("unit"))
        components_touched += 1

    for mat_code, by_slot in defaults_by_mat.items():
        _ensure_material_stub(con, code=mat_code)
        material_id = int(con.execute("SELECT material_id FROM materials WHERE code = ?", [mat_code]).fetchone()[0])
        for slot_key, comp_code2 in by_slot.items():
            row = con.execute("SELECT component_id FROM components WHERE code = ? LIMIT 1", [comp_code2]).fetchone()
            if row is None:
                continue
            component_id = int(row[0])
            con.execute(
                """
                INSERT INTO material_component_defaults(material_id, slot_key, component_id)
                VALUES (?, ?, ?)
                ON CONFLICT(material_id, slot_key) DO UPDATE SET component_id=excluded.component_id
                """,
                [int(material_id), str(slot_key), int(component_id)],
            )
            defaults_touched += 1

    progress(
        f"Components imported/updated: types={types_touched}, components={components_touched}, defaults={defaults_touched}"
    )
    return (types_touched, components_touched, defaults_touched)


def _ensure_material_stub(con, *, code: str) -> None:
    con.execute(
        """
        INSERT INTO materials(material_id, code, description, active)
        VALUES (?, ?, NULL, TRUE)
        ON CONFLICT(code) DO NOTHING
        """,
        [new_id(), code.strip(),],
    )


def _ensure_component_type(con, name: str) -> bool:
    name = name.strip()
    if not name:
        return False

    inferred = _slot_key_for_type(name)
    row = con.execute("SELECT type_id, slot_key FROM component_types WHERE name = ?", [name]).fetchone()
    if row is None:
        con.execute(
            """
            INSERT INTO component_types(type_id, name, slot_key, active)
            VALUES (?, ?, ?, TRUE)
            """,
            [new_id(), name, inferred],
        )
        return True
    return False


def _upsert_component(con, *, type_id: int, code: str, description: str | None, unit: str | None) -> None:
    code = code.strip()
    row = con.execute(
        "SELECT component_id, type_id, description, unit, active FROM components WHERE code = ? LIMIT 1",
        [code],
    ).fetchone()
    if row is None:
        con.execute(
            """
            INSERT INTO components(component_id, type_id, code, description, unit, active)
            VALUES (?, ?, ?, ?, ?, TRUE)
            """,
            [new_id(), int(type_id), code, description, unit],
        )
        return

    desired_description = description if description is not None else row[2]
    desired_unit = unit if unit is not None else row[3]
    if (
        int(row[1]) == int(type_id)
        and row[2] == desired_description
        and row[3] == desired_unit
        and bool(row[4])
    ):
        return

    con.execute(
        """
        UPDATE components
        SET
            type_id=?,
            description=COALESCE(?, description),
            unit=COALESCE(?, unit),
            active=TRUE
        WHERE code=?
        """,
        [int(type_id), description, unit, code],
    )


def _slot_key_for_type(type_name: str) -> str | None:
    if not type_name:
        return None
    key = " ".join(type_name.strip().lower().split())
    return _TYPE_TO_SLOT_KEY.get(key)


def _cell_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None
