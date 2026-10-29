from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class RoleRow:
    role_id: int
    name: str
    can_edit_master: bool
    can_edit_tests: bool
    can_manage_users: bool
    can_send_outlook: bool


def list_roles(con) -> list[RoleRow]:
    rows = con.execute(
        """
        SELECT role_id, name, can_edit_master, can_edit_tests, can_manage_users, can_send_outlook
        FROM roles
        ORDER BY name
        """
    ).fetchall()
    return [
        RoleRow(int(r[0]), str(r[1]), bool(r[2]), bool(r[3]), bool(r[4]), bool(r[5]))
        for r in rows
    ]


def upsert_role(
    con,
    *,
    role_id: int | None,
    name: str,
    can_edit_master: bool,
    can_edit_tests: bool,
    can_manage_users: bool,
    can_send_outlook: bool,
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Role name is required.")

    if role_id is None:
        role_id = new_id()
        con.execute(
            """
            INSERT INTO roles(role_id, name, can_edit_master, can_edit_tests, can_manage_users, can_send_outlook)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [role_id, name, bool(can_edit_master), bool(can_edit_tests), bool(can_manage_users), bool(can_send_outlook)],
        )
        return int(role_id)

    con.execute(
        """
        UPDATE roles
        SET name=?, can_edit_master=?, can_edit_tests=?, can_manage_users=?, can_send_outlook=?
        WHERE role_id=?
        """,
        [name, bool(can_edit_master), bool(can_edit_tests), bool(can_manage_users), bool(can_send_outlook), int(role_id)],
    )
    return int(role_id)


def delete_role(con, *, role_id: int) -> None:
    con.execute("DELETE FROM roles WHERE role_id = ?", [int(role_id)])

