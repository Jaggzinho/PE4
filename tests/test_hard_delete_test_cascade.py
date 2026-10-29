from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.tests_repo import hard_delete_test
from pe3_qc_app.services.time_utils import utc_now_naive


class TestHardDeleteTestCascade(unittest.TestCase):
    def test_deletes_test_and_dependents(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_hard_delete.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

        mid = new_id()
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'MAT001', 'Material 001', NULL, NULL, NULL, NULL, TRUE)
            """,
            [int(mid)],
        )
        test_id = new_id()
        con.execute(
            """
            INSERT INTO tests(
                test_id, material_id, request_date, prod_date, analysis_date,
                notes, created_by, created_at, deleted_at, external_source, external_row_key
            )
            VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, ?, NULL, 'Manual', ?)
            """,
            [int(test_id), int(mid), utc_now_naive(), str(int(test_id))],
        )
        pid = new_id()
        con.execute(
            "INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) VALUES (?, 'P', NULL, 'num', TRUE, NULL)",
            [int(pid)],
        )
        con.execute(
            "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (?, ?, ?, 1.0, NULL)",
            [int(new_id()), int(test_id), int(pid)],
        )
        con.execute(
            "INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code) VALUES (?, 'ISO', 'C', 'D', 'L')",
            [int(test_id)],
        )

        # Simulate a legacy dependent table that still references tests(test_id).
        con.execute(
            """
            CREATE TABLE legacy_test_links(
                link_id BIGINT PRIMARY KEY,
                test_id BIGINT NOT NULL REFERENCES tests(test_id)
            );
            """
        )
        con.execute("INSERT INTO legacy_test_links(link_id, test_id) VALUES (1, ?)", [int(test_id)])

        hard_delete_test(con, test_id=int(test_id))

        self.assertEqual(int(con.execute("SELECT COUNT(*) FROM tests WHERE test_id=?", [int(test_id)]).fetchone()[0]), 0)
        self.assertEqual(int(con.execute("SELECT COUNT(*) FROM measurements WHERE test_id=?", [int(test_id)]).fetchone()[0]), 0)
        self.assertEqual(int(con.execute("SELECT COUNT(*) FROM test_component_lots WHERE test_id=?", [int(test_id)]).fetchone()[0]), 0)
        self.assertEqual(int(con.execute("SELECT COUNT(*) FROM legacy_test_links WHERE test_id=?", [int(test_id)]).fetchone()[0]), 0)
        con.close()


if __name__ == "__main__":
    unittest.main()
