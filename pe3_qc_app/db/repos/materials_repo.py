from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class Material:
    material_id: int
    code: str
    description: str | None
    lastrina_code: str | None
    lastrina_desc: str | None
    active: bool


def list_materials(con) -> list[Material]:
    rows = con.execute(
        """
        SELECT material_id, code, description, lastrina_code, lastrina_desc, active
        FROM materials
        ORDER BY code
        """
    ).fetchall()
    return [
        Material(
            material_id=int(r[0]),
            code=str(r[1]),
            description=(str(r[2]) if r[2] is not None else None),
            lastrina_code=(str(r[3]) if r[3] is not None else None),
            lastrina_desc=(str(r[4]) if r[4] is not None else None),
            active=bool(r[5]),
        )
        for r in rows
    ]


def get_material(con, *, material_id: int) -> Material | None:
    row = con.execute(
        """
        SELECT material_id, code, description, lastrina_code, lastrina_desc, active
        FROM materials
        WHERE material_id = ?
        LIMIT 1
        """,
        [int(material_id)],
    ).fetchone()
    if row is None:
        return None
    return Material(
        material_id=int(row[0]),
        code=str(row[1]),
        description=(str(row[2]) if row[2] is not None else None),
        lastrina_code=(str(row[3]) if row[3] is not None else None),
        lastrina_desc=(str(row[4]) if row[4] is not None else None),
        active=bool(row[5]),
    )


def upsert_material(
    con,
    *,
    material_id: int | None,
    code: str,
    description: str | None,
    lastrina_code: str | None,
    lastrina_desc: str | None,
    active: bool,
) -> int:
    code = code.strip()
    if not code:
        raise ValueError("Material code is required.")

    if material_id is None:
        material_id = new_id()
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            [material_id, code, description, lastrina_code, lastrina_desc, bool(active)],
        )
        return int(material_id)

    con.execute(
        """
        UPDATE materials
        SET code=?, description=?, lastrina_code=?, lastrina_desc=?, active=?
        WHERE material_id=?
        """,
        [code, description, lastrina_code, lastrina_desc, bool(active), int(material_id)],
    )
    return int(material_id)


def delete_material(con, *, material_id: int) -> None:
    con.execute("DELETE FROM materials WHERE material_id = ?", [int(material_id)])
