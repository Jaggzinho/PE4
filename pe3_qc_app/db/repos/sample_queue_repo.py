from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.services.time_utils import utc_now_naive


@dataclass(frozen=True)
class QueueRow:
    item_id: int
    machine_code: str | None
    material_code: str | None
    description: str | None
    lastrina_code: str | None
    last_request_date: date | None


def enqueue_item(con, *, user_id: int, item_id: int) -> None:
    qid = new_id()
    con.execute(
        """
        INSERT INTO sample_request_queue(queue_id, user_id, item_id, added_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, item_id) DO NOTHING
        """,
        [int(qid), int(user_id), int(item_id), utc_now_naive()],
    )


def remove_item(con, *, user_id: int, item_id: int) -> None:
    con.execute(
        """
        DELETE FROM sample_request_queue
        WHERE user_id = ? AND item_id = ?
        """,
        [int(user_id), int(item_id)],
    )


def clear_queue(con, *, user_id: int) -> None:
    con.execute("DELETE FROM sample_request_queue WHERE user_id = ?", [int(user_id)])


def list_queue_rows(con, *, user_id: int) -> list[QueueRow]:
    rows = con.execute(
        """
        WITH last_req AS (
            SELECT material_id, MAX(request_date) AS last_request_date
            FROM tests
            WHERE deleted_at IS NULL
            GROUP BY material_id
        )
        SELECT
            s.item_id,
            s.machine_code,
            m.code AS material_code,
            s.description,
            m.lastrina_code,
            lr.last_request_date
        FROM sample_request_queue q
        JOIN sinottico_items s ON s.item_id = q.item_id
        LEFT JOIN materials m ON m.material_id = s.material_id
        LEFT JOIN last_req lr ON lr.material_id = s.material_id
        WHERE q.user_id = ?
        ORDER BY q.added_at, q.queue_id
        """,
        [int(user_id)],
    ).fetchall()
    out: list[QueueRow] = []
    for r in rows:
        out.append(
            QueueRow(
                item_id=int(r[0]),
                machine_code=(str(r[1]) if r[1] is not None else None),
                material_code=(str(r[2]) if r[2] is not None else None),
                description=(str(r[3]) if r[3] is not None else None),
                lastrina_code=(str(r[4]) if r[4] is not None else None),
                last_request_date=r[5],
            )
        )
    return out

