from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.sample_queue_repo import clear_queue, enqueue_item, list_queue_rows, remove_item
from pe3_qc_app.services.time_utils import utc_now_naive


class TestSampleQueueRepo(unittest.TestCase):
    def test_enqueue_list_remove_clear(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_sample_queue.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

        user_id = new_id()
        con.execute(
            """
            INSERT INTO users(user_id, username, pw_salt, pw_hash, role_id, active, created_at, last_login_at)
            VALUES (?, 'u1', ?, ?, 1, TRUE, ?, NULL)
            """,
            [int(user_id), b"salt", b"hash", utc_now_naive()],
        )

        mid = new_id()
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'MAT001', 'Material 001', 'L001', NULL, NULL, NULL, TRUE)
            """,
            [int(mid)],
        )
        item_id = new_id()
        con.execute(
            """
            INSERT INTO sinottico_items(item_id, machine_code, excel_label, excel_code, description, material_id, sort_order, active)
            VALUES (?, 'MAC 1', 'X', 'MAT001', 'Material 001', ?, 1, TRUE)
            """,
            [int(item_id), int(mid)],
        )
        con.execute(
            """
            INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
            VALUES (?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, 'Manual', ?)
            """,
            [int(new_id()), int(mid), date(2026, 4, 20), utc_now_naive(), "x"],
        )

        enqueue_item(con, user_id=int(user_id), item_id=int(item_id))
        enqueue_item(con, user_id=int(user_id), item_id=int(item_id))
        rows = list_queue_rows(con, user_id=int(user_id))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].item_id, int(item_id))
        self.assertEqual(rows[0].material_code, "MAT001")
        self.assertEqual(rows[0].last_request_date, date(2026, 4, 20))

        remove_item(con, user_id=int(user_id), item_id=int(item_id))
        self.assertEqual(list_queue_rows(con, user_id=int(user_id)), [])

        enqueue_item(con, user_id=int(user_id), item_id=int(item_id))
        clear_queue(con, user_id=int(user_id))
        self.assertEqual(list_queue_rows(con, user_id=int(user_id)), [])

        con.close()


if __name__ == "__main__":
    unittest.main()

