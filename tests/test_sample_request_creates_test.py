from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.outlook_repo import log_sample_request
from pe3_qc_app.db.repos.sinottico_repo import list_dashboard_rows
from pe3_qc_app.db.repos.tests_repo import create_test_for_sample_request


class TestSampleRequestCreatesTest(unittest.TestCase):
    def test_creates_test_and_updates_sinottico_last_request(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_sample_req.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

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

        req_id = log_sample_request(
            con,
            item_id=int(item_id),
            requested_by=None,
            outcome="sent",
            subject="s",
            to_list="t",
            cc_list="c",
        )
        d = date(2026, 4, 20)
        test_id = create_test_for_sample_request(con, item_id=int(item_id), req_id=int(req_id), request_date=d, requested_by=None)
        self.assertIsNotNone(test_id)

        rows = list_dashboard_rows(con)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].last_request_date, d)
        con.close()


if __name__ == "__main__":
    unittest.main()
