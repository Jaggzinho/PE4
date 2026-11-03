"""Shared account schema and non-authenticating local QC identity references."""
from __future__ import annotations

from secrets import token_bytes

from pe3_qc_app.core.context import Session


def initialize(con, *, roles: list[tuple], users: list[tuple]) -> None:
    # Independent, numbered identity schema. Never migrate or attach a QC file here.
    con.execute("CREATE TABLE IF NOT EXISTS identity_schema_version(version INTEGER PRIMARY KEY)")
    versions = con.execute("SELECT version FROM identity_schema_version").fetchall()
    if versions:
        if versions != [(1,)]:
            raise RuntimeError("Unsupported shared identity schema version")
        return
    con.execute("""
        CREATE TABLE roles(
            role_id BIGINT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            can_edit_master BOOLEAN NOT NULL, can_edit_tests BOOLEAN NOT NULL,
            can_manage_users BOOLEAN NOT NULL, can_send_outlook BOOLEAN NOT NULL
        );
        CREATE TABLE users(
            user_id BIGINT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            pw_salt BLOB NOT NULL, pw_hash BLOB NOT NULL,
            role_id BIGINT NOT NULL REFERENCES roles(role_id),
            active BOOLEAN NOT NULL, created_at TIMESTAMP NOT NULL, last_login_at TIMESTAMP
        );
    """)
    for row in roles:
        con.execute("INSERT INTO roles VALUES (?, ?, ?, ?, ?, ?)", row)
    for row in users:
        con.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)
    con.execute("INSERT INTO identity_schema_version VALUES (1)")


def snapshot(con) -> tuple[list[tuple], list[tuple]]:
    return (
        con.execute("SELECT role_id, name, can_edit_master, can_edit_tests, can_manage_users, can_send_outlook FROM roles").fetchall(),
        con.execute("SELECT user_id, username, pw_salt, pw_hash, role_id, active, created_at, last_login_at FROM users").fetchall(),
    )


def session_for_user(con, user_id: int) -> Session | None:
    row = con.execute("""
        SELECT u.user_id, u.username, r.name, r.can_edit_master, r.can_edit_tests,
               r.can_manage_users, r.can_send_outlook
        FROM users u JOIN roles r ON r.role_id = u.role_id
        WHERE u.user_id = ? AND u.active
    """, [user_id]).fetchone()
    if row is None:
        return None
    return Session(int(row[0]), row[1], row[2], dict(zip(
        ("can_edit_master", "can_edit_tests", "can_manage_users", "can_send_outlook"),
        map(bool, row[3:]),
    )))


def ensure_projection(con, session: Session) -> None:
    if con.execute("SELECT 1 FROM users WHERE user_id = ?", [session.user_id]).fetchone():
        return
    # Keep the legacy NOT NULL credential columns and FKs intact. Random bytes
    # are not password hashes; the projection is inactive and never authenticates.
    con.execute("""
        INSERT INTO roles VALUES (-1, '__shared_identity__', FALSE, FALSE, FALSE, FALSE)
        ON CONFLICT(role_id) DO NOTHING
    """)
    con.execute("""
        INSERT INTO users(user_id, username, pw_salt, pw_hash, role_id, active, created_at)
        VALUES (?, ?, ?, ?, -1, FALSE, current_timestamp)
    """, [session.user_id, session.username, token_bytes(32), token_bytes(32)])


def has_qc_references(con, user_id: int) -> bool:
    return any(con.execute(sql, [user_id]).fetchone() for sql in (
        "SELECT 1 FROM tests WHERE created_by = ? LIMIT 1",
        "SELECT 1 FROM sample_requests WHERE requested_by = ? LIMIT 1",
        "SELECT 1 FROM sample_request_queue WHERE user_id = ? LIMIT 1",
        "SELECT 1 FROM import_jobs WHERE owner_id = ? LIMIT 1",
    ))


def remove_projection(con, user_id: int) -> None:
    con.execute("DELETE FROM users WHERE user_id = ?", [user_id])
