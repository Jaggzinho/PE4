from __future__ import annotations

from dataclasses import dataclass

from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class Contact:
    contact_id: int
    name: str | None
    email: str
    group_name: str
    active: bool


def list_contacts(con) -> list[Contact]:
    rows = con.execute(
        """
        SELECT contact_id, name, email, group_name, active
        FROM contacts
        ORDER BY group_name, email
        """
    ).fetchall()
    return [
        Contact(
            contact_id=int(r[0]),
            name=(str(r[1]) if r[1] is not None else None),
            email=str(r[2]),
            group_name=str(r[3]),
            active=bool(r[4]),
        )
        for r in rows
    ]


def upsert_contact(
    con,
    *,
    contact_id: int | None,
    name: str | None,
    email: str,
    group_name: str,
    active: bool,
) -> int:
    email = email.strip()
    group_name = group_name.strip()
    if not email or "@" not in email:
        raise ValueError("Valid email is required.")
    if not group_name:
        raise ValueError("Group name is required.")
    if name is not None:
        name = name.strip() or None

    if contact_id is None:
        contact_id = new_id()
        con.execute(
            """
            INSERT INTO contacts(contact_id, name, email, group_name, active)
            VALUES (?, ?, ?, ?, ?)
            """,
            [contact_id, name, email, group_name, bool(active)],
        )
        return int(contact_id)

    con.execute(
        """
        UPDATE contacts SET name=?, email=?, group_name=?, active=? WHERE contact_id=?
        """,
        [name, email, group_name, bool(active), int(contact_id)],
    )
    return int(contact_id)


def delete_contact(con, *, contact_id: int) -> None:
    con.execute("DELETE FROM contacts WHERE contact_id = ?", [int(contact_id)])

