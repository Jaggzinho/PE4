from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.services.qc_failures_service import fetch_alarm_tolerance_failures
from pe3_qc_app.services.time_utils import utc_now_naive


class TestQcFailuresService(unittest.TestCase):
    def _db(self):
        dbp = Path(tempfile.gettempdir()) / "pe3_test_qc_failures_service.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)
        return con

    def test_lists_only_alarm_failures_with_tolerance(self) -> None:
        con = self._db()
        try:
            con.execute(
                """
                INSERT INTO users(user_id, username, pw_salt, pw_hash, role_id, active, created_at, last_login_at)
                VALUES (1, 'u', ?, ?, 1, TRUE, ?, NULL)
                """,
                [b"s", b"h", utc_now_naive()],
            )
            con.execute(
                """
                INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
                VALUES (10, 'MAT', 'M', NULL, NULL, NULL, NULL, TRUE)
                """
            )
            con.execute("INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) VALUES (101, 'P1', NULL, 'num', TRUE, 1)")
            con.execute("INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) VALUES (102, 'P2', NULL, 'num', TRUE, 2)")

            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1000, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'a')
                """,
                [date(2026, 4, 1), utc_now_naive()],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2000, 1000, 101, 50.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1000, 102, 123.0, NULL)")

            # Only P1 has tolerance; it fails alarm.
            con.execute(
                """
                INSERT INTO tolerances(tolerance_id, material_id, property_id, warn_low, warn_high, alarm_low, alarm_high, updated_at)
                VALUES (9000, 10, 101, NULL, NULL, 60.0, 80.0, ?)
                """,
                [utc_now_naive()],
            )

            ctx, rows = fetch_alarm_tolerance_failures(con, test_id=1000)
            self.assertEqual(ctx.test_id, 1000)
            self.assertEqual(ctx.material_code, "MAT")
            self.assertEqual(ctx.request_date, date(2026, 4, 1))
            self.assertEqual([r.property_name for r in rows], ["P1"])
            self.assertTrue(rows[0].actual_value)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()

