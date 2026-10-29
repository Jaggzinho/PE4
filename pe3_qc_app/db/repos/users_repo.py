from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pe3_qc_app.services.time_utils import utc_now_naive

from pe3_qc_app.auth.passwords import hash_password
from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class UserRow:
    user_id: int
    username: str
    role_id: int
    role_name: str
    active: bool
    created_at: datetime
    last_login_at: datetime | None


def list_users(con) -> list[UserRow]:
    rows = con.execute(
        """
        SELECT u.user_id, u.username, u.role_id, r.name, u.active, u.created_at, u.last_login_at
        FROM users u
        JOIN roles r ON r.role_id = u.role_id
        ORDER BY u.username
        """
    ).fetchall()
    out: list[UserRow] = []
    for r in rows:
        out.append(
            UserRow(
                user_id=int(r[0]),
                username=str(r[1]),
                role_id=int(r[2]),
                role_name=str(r[3]),
                active=bool(r[4]),
                created_at=r[5],
                last_login_at=r[6],
            )
        )
    return out


def create_user(con, *, username: str, password: str, role_id: int, active: bool = True) -> int:
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if not password:
        raise ValueError("Password is required.")
    salt, pw_hash = hash_password(password)
    uid = new_id()
    con.execute(
        """
        INSERT INTO users(user_id, username, pw_salt, pw_hash, role_id, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [uid, username, salt, pw_hash, int(role_id), bool(active), utc_now_naive()],
    )
    return int(uid)


def update_user(con, *, user_id: int, role_id: int, active: bool) -> None:
    con.execute(
        "UPDATE users SET role_id=?, active=? WHERE user_id=?",
        [int(role_id), bool(active), int(user_id)],
    )


def reset_password(con, *, user_id: int, new_password: str) -> None:
    if not new_password:
        raise ValueError("Password is required.")
    salt, pw_hash = hash_password(new_password)
    con.execute("UPDATE users SET pw_salt=?, pw_hash=? WHERE user_id=?", [salt, pw_hash, int(user_id)])


def delete_user(con, *, user_id: int) -> None:
    con.execute("DELETE FROM users WHERE user_id = ?", [int(user_id)])
