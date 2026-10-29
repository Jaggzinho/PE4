from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.rating_repo import upsert_rule, upsert_weight
from pe3_qc_app.services.rating_service import compute_average_ratings_for_materials
from pe3_qc_app.services.time_utils import utc_now_naive


class TestRatingAverage(unittest.TestCase):
    def _db(self):
        dbp = Path(tempfile.gettempdir()) / "pe3_test_rating_average.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)
        return con

    def _seed_minimal(self, con) -> None:
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
        con.execute("INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) VALUES (999, 'IGNORED', NULL, 'num', TRUE, 9)")

        upsert_weight(con, property_id=101, weight=1.0)
        upsert_weight(con, property_id=102, weight=1.0)
        upsert_rule(
            con,
            property_id=101,
            rule_json={
                "type": "pct_from_avg_bands_v1",
                "max_points": 20,
                "bands": [{"max_pct": 1.0, "points": 20}, {"max_pct": None, "points": 0}],
            },
        )
        upsert_rule(
            con,
            property_id=102,
            rule_json={
                "type": "pct_from_avg_bands_v1",
                "max_points": 20,
                "bands": [{"max_pct": 1.0, "points": 20}, {"max_pct": None, "points": 0}],
            },
        )

    def test_average_two_tests_skips_non_contributing_and_deleted(self) -> None:
        con = self._db()
        try:
            self._seed_minimal(con)

            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES
                    (1000, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'a'),
                    (1001, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'b'),
                    (1002, 10, ?, NULL, NULL, NULL, 1, ?, ?, 'Manual', 'c'),
                    (1003, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'd')
                """,
                [
                    date(2026, 4, 1),
                    utc_now_naive(),
                    date(2026, 4, 2),
                    utc_now_naive(),
                    date(2026, 4, 3),
                    utc_now_naive(),
                    utc_now_naive(),  # deleted_at
                    date(2026, 4, 4),
                    utc_now_naive(),
                ],
            )

            # Two contributing tests: one perfect, one far from avg on P2.
            # Test 1000 values
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2000, 1000, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1000, 102, 100.0, NULL)")

            # Test 1001 values (P2 far)
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2010, 1001, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2011, 1001, 102, 130.0, NULL)")

            # Deleted test 1002 (should be ignored)
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2020, 1002, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2021, 1002, 102, 100.0, NULL)")

            # Non-contributing-only test 1003 (ignored property only) => should be skipped
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2030, 1003, 999, 1.0, NULL)")

            res = compute_average_ratings_for_materials(con, material_ids=[10])
            self.assertIn(10, res)
            avg = float(res[10])

            # Compute expected:
            # All-time averages per property across non-deleted tests (1000,1001,1003):
            # P1 avg = 100
            # P2 avg = (100 + 130) / 2 = 115
            # Test 1000:
            #  - P1 pct_dist 0 -> 100%
            #  - P2 pct_dist |100-115|/115*100 ~ 13.04% -> 0%
            #  => (100 + 0)/2 = 50
            # Test 1001:
            #  - P1 pct_dist 0 -> 100%
            #  - P2 pct_dist |130-115|/115*100 ~ 13.04% -> 0%
            #  => (100 + 0)/2 = 50
            # Average across tests = 50
            self.assertAlmostEqual(avg, 50.0, places=6)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()

