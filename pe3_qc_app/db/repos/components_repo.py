from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class Component:
    component_id: int
    type_id: int
    type_name: str
    slot_key: str | None
    code: str
    description: str | None
    unit: str | None
    active: bool


def list_components(con, *, include_inactive: bool = True) -> list[Component]:
    where = "" if include_inactive else "WHERE c.active"
    rows = con.execute(
        f"""
        SELECT
            c.component_id,
            c.type_id,
            t.name,
            t.slot_key,
            c.code,
            c.description,
            c.unit,
            c.active
        FROM components c
        JOIN component_types t ON t.type_id = c.type_id
        {where}
        ORDER BY t.name, c.code
        """
    ).fetchall()
    out: list[Component] = []
    for r in rows:
        out.append(
            Component(
                component_id=int(r[0]),
                type_id=int(r[1]),
                type_name=str(r[2]),
                slot_key=(str(r[3]) if r[3] is not None and str(r[3]).strip() else None),
                code=str(r[4]),
                description=(str(r[5]) if r[5] is not None else None),
                unit=(str(r[6]) if r[6] is not None else None),
                active=bool(r[7]),
            )
        )
    return out


def upsert_component(
    con,
    *,
    component_id: int | None,
    type_id: int,
    code: str,
    description: str | None,
    unit: str | None,
    active: bool,
) -> int:
    code = code.strip()
    if not code:
        raise ValueError("Component code is required.")

    if component_id is None:
        component_id = new_id()
        con.execute(
            """
            INSERT INTO components(component_id, type_id, code, description, unit, active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [int(component_id), int(type_id), code, description, unit, bool(active)],
        )
        return int(component_id)

    con.execute(
        """
        UPDATE components
        SET type_id=?, code=?, description=?, unit=?, active=?
        WHERE component_id=?
        """,
        [int(type_id), code, description, unit, bool(active), int(component_id)],
    )
    return int(component_id)


def delete_component(con, *, component_id: int) -> None:
    con.execute("DELETE FROM components WHERE component_id = ?", [int(component_id)])

