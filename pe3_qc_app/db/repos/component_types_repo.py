from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class ComponentType:
    type_id: int
    name: str
    slot_key: str | None
    active: bool


def list_component_types(con, *, include_inactive: bool = True) -> list[ComponentType]:
    where = "" if include_inactive else "WHERE active"
    rows = con.execute(
        f"""
        SELECT type_id, name, slot_key, active
        FROM component_types
        {where}
        ORDER BY COALESCE(slot_key, 'ZZZ'), name
        """
    ).fetchall()
    return [
        ComponentType(
            type_id=int(r[0]),
            name=str(r[1]),
            slot_key=(str(r[2]) if r[2] is not None and str(r[2]).strip() else None),
            active=bool(r[3]),
        )
        for r in rows
    ]


def upsert_component_type(
    con,
    *,
    type_id: int | None,
    name: str,
    slot_key: str | None,
    active: bool,
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Type name is required.")
    slot_key = (slot_key.strip() if slot_key else None) or None

    if type_id is None:
        type_id = new_id()
        con.execute(
            """
            INSERT INTO component_types(type_id, name, slot_key, active)
            VALUES (?, ?, ?, ?)
            """,
            [int(type_id), name, slot_key, bool(active)],
        )
        return int(type_id)

    con.execute(
        """
        UPDATE component_types
        SET name=?, slot_key=?, active=?
        WHERE type_id=?
        """,
        [name, slot_key, bool(active), int(type_id)],
    )
    return int(type_id)


def delete_component_type(con, *, type_id: int) -> None:
    con.execute("DELETE FROM component_types WHERE type_id = ?", [int(type_id)])

