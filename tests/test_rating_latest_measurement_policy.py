from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.rating_repo import upsert_rule, upsert_weight
from pe3_qc_app.services.rating_service import compute_material_rating
from pe3_qc_app.services.time_utils import utc_now_naive


class TestRatingLatestMeasurementPolicy(unittest.TestCase):
    def _db(self):
        dbp = Path(tempfile.gettempdir()) / "pe3_test_rating_latest_policy.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)
        return con

    def test_latest_uses_coalesce_date_then_test_id_then_measurement_id(self) -> None:
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
            con.execute("INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) VALUES (101, 'P', NULL, 'num', TRUE, 1)")

            upsert_weight(con, property_id=101, weight=1.0)
            upsert_rule(
                con,
                property_id=101,
                rule_json={
                    "type": "pct_from_avg_bands_v1",
                    "max_points": 20,
                    "bands": [
                        {"max_pct": 1.0, "points": 20},
                        {"max_pct": None, "points": 0},
                    ],
                },
            )

            # Create 3 tests so avg is stable and known.
            # Values: 100, 110, 90 => avg = 100.

            # test_id 1001 has later request_date, but no analysis_date (value=100).
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1001, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'a')
                """,
                [date(2026, 4, 10), utc_now_naive()],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1001, 101, 100.0, NULL)")

            # test_id 1002 has earlier request_date but later analysis_date -> should win by COALESCE (value=110).
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1002, 10, ?, NULL, ?, NULL, 1, ?, NULL, 'Manual', 'b')
                """,
                [date(2026, 4, 1), date(2026, 4, 20), utc_now_naive()],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2002, 1002, 101, 110.0, NULL)")

            # Older test for avg stability (value=90).
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (900, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'z')
                """,
                [date(2026, 3, 1), utc_now_naive()],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (9001, 900, 101, 90.0, NULL)")

            r = compute_material_rating(con, material_id=10)
            self.assertIsNotNone(r)
            # Latest should be value=110 (avg=100 => 10% dist => 0 points => 0%).
            self.assertAlmostEqual(float(r), 0.0, places=6)

            # Same COALESCE date, higher test_id wins (value=100 => 0% dist => 100%).
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1003, 10, ?, NULL, ?, NULL, 1, ?, NULL, 'Manual', 'c')
                """,
                [date(2026, 4, 2), date(2026, 4, 20), utc_now_naive()],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2003, 1003, 101, 100.0, NULL)")

            r2 = compute_material_rating(con, material_id=10)
            self.assertIsNotNone(r2)
            self.assertAlmostEqual(float(r2), 100.0, places=6)

            # Within a test, higher measurement_id wins (overwrite latest test's value to 110 => 0%).
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2004, 1003, 101, 110.0, NULL)")
            r3 = compute_material_rating(con, material_id=10)
            self.assertIsNotNone(r3)
            self.assertAlmostEqual(float(r3), 0.0, places=6)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
