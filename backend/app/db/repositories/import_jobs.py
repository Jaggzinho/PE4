"""Persistent metadata for local import jobs; workbook data has its own transaction."""

from __future__ import annotations

import json


_COLUMNS = "job_id, owner_id, kind, status, progress, messages_json, result_json, error, created_at, updated_at"


def _record(row) -> dict | None:
    if row is None:
        return None
    return {
        "job_id": row[0], "owner_id": int(row[1]), "kind": row[2], "status": row[3],
        "progress": int(row[4]), "messages": json.loads(row[5]),
        "result": json.loads(row[6]) if row[6] is not None else None,
        "error": row[7], "created_at": row[8], "updated_at": row[9],
    }


def insert(con, snapshot) -> None:
    con.execute(
        f"INSERT INTO import_jobs({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [snapshot.job_id, snapshot.owner_id, snapshot.kind, snapshot.status, snapshot.progress,
         json.dumps(snapshot.messages), json.dumps(snapshot.result) if snapshot.result is not None else None,
         snapshot.error, snapshot.created_at, snapshot.updated_at],
    )


def update(con, snapshot) -> None:
    con.execute(
        """UPDATE import_jobs SET status=?, progress=?, messages_json=?, result_json=?, error=?, updated_at=?
           WHERE job_id=?""",
        [snapshot.status, snapshot.progress, json.dumps(snapshot.messages),
         json.dumps(snapshot.result) if snapshot.result is not None else None,
         snapshot.error, snapshot.updated_at, snapshot.job_id],
    )


def get(con, job_id: str) -> dict | None:
    return _record(con.execute(f"SELECT {_COLUMNS} FROM import_jobs WHERE job_id=?", [job_id]).fetchone())


def list_recent(con, *, owner_id: int, can_manage: bool, limit: int) -> list[dict]:
    where = "" if can_manage else "WHERE owner_id=?"
    params = [] if can_manage else [owner_id]
    rows = con.execute(
        f"SELECT {_COLUMNS} FROM import_jobs {where} ORDER BY created_at DESC, job_id DESC LIMIT ?",
        [*params, limit],
    ).fetchall()
    return [_record(row) for row in rows]


def recover_interrupted(con, *, now, message: str) -> None:
    con.execute(
        """UPDATE import_jobs SET status='failed', error=?, updated_at=?
           WHERE status IN ('queued', 'running')""",
        [message, now],
    )


def prune_terminal(con, *, keep: int) -> None:
    con.execute(
        """DELETE FROM import_jobs WHERE job_id IN (
             SELECT job_id FROM import_jobs WHERE status IN ('succeeded', 'failed')
             ORDER BY created_at DESC, job_id DESC OFFSET ?
           )""",
        [keep],
    )
