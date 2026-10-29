from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pe3_qc_app.auth.passwords import hash_password, verify_password
from pe3_qc_app.core.context import Session
from pe3_qc_app.db.ids import new_id


@dataclass(frozen=True)
class Role:
    role_id: int
    name: str
    can_edit_master: bool
    can_edit_tests: bool
    can_manage_users: bool
    can_send_outlook: bool

    def permissions_dict(self) -> dict[str, bool]:
        return {
            "can_edit_master": bool(self.can_edit_master),
            "can_edit_tests": bool(self.can_edit_tests),
            "can_manage_users": bool(self.can_manage_users),
            "can_send_outlook": bool(self.can_send_outlook),
        }


def any_users(con) -> bool:
    row = con.execute("SELECT COUNT(*) FROM users").fetchone()
    return bool(row and int(row[0]) > 0)


def list_roles(con) -> list[Role]:
    rows = con.execute(
        """
        SELECT role_id, name, can_edit_master, can_edit_tests, can_manage_users, can_send_outlook
        FROM roles
        ORDER BY name
        """
    ).fetchall()
    return [Role(int(r[0]), str(r[1]), bool(r[2]), bool(r[3]), bool(r[4]), bool(r[5])) for r in rows]


def get_role_by_name(con, role_name: str) -> Role | None:
    row = con.execute(
        """
        SELECT role_id, name, can_edit_master, can_edit_tests, can_manage_users, can_send_outlook
        FROM roles
        WHERE name = ?
        """,
        [role_name],
    ).fetchone()
    if row is None:
        return None
    return Role(int(row[0]), str(row[1]), bool(row[2]), bool(row[3]), bool(row[4]), bool(row[5]))


def create_user(con, *, username: str, password: str, role_name: str) -> int:
    role = get_role_by_name(con, role_name)
    if role is None:
        raise ValueError(f"Unknown role: {role_name}")
    salt, pw_hash = hash_password(password)
    uid = new_id()
    now = datetime.utcnow()
    con.execute(
        """
        INSERT INTO users(user_id, username, pw_salt, pw_hash, role_id, active, created_at)
        VALUES (?, ?, ?, ?, ?, TRUE, ?)
        """,
        [uid, username.strip(), salt, pw_hash, role.role_id, now],
    )
    return int(uid)


def authenticate(con, *, username: str, password: str) -> Session | None:
    row = con.execute(
        """
        SELECT
            u.user_id,
            u.username,
            u.pw_salt,
            u.pw_hash,
            u.active,
            r.name,
            r.can_edit_master,
            r.can_edit_tests,
            r.can_manage_users,
            r.can_send_outlook
        FROM users u
        JOIN roles r ON r.role_id = u.role_id
        WHERE u.username = ?
        """,
        [username.strip()],
    ).fetchone()
    if row is None:
        return None
    if not bool(row[4]):
        return None
    salt = bytes(row[2])
    expected = bytes(row[3])
    if not verify_password(password, salt=salt, expected_hash=expected):
        return None

    con.execute("UPDATE users SET last_login_at = ? WHERE user_id = ?", [datetime.utcnow(), int(row[0])])
    perms = {
        "can_edit_master": bool(row[6]),
        "can_edit_tests": bool(row[7]),
        "can_manage_users": bool(row[8]),
        "can_send_outlook": bool(row[9]),
    }
    return Session(user_id=int(row[0]), username=str(row[1]), role_name=str(row[5]), permissions=perms)

