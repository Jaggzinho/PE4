from __future__ import annotations


def get_material_component_defaults(con, *, material_id: int) -> dict[str, dict[str, str | None]]:
    rows = con.execute(
        """
        SELECT mcd.slot_key, c.code, c.description
        FROM material_component_defaults mcd
        JOIN components c ON c.component_id = mcd.component_id
        WHERE mcd.material_id = ?
        """,
        [int(material_id)],
    ).fetchall()
    out: dict[str, dict[str, str | None]] = {}
    for slot_key, code, desc in rows:
        sk = str(slot_key)
        out[sk] = {
            "code": (str(code) if code is not None else None),
            "desc": (str(desc) if desc is not None else None),
        }
    return out

