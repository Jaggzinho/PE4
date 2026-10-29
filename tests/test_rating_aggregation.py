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


class TestRatingAggregation(unittest.TestCase):
    def _db(self):
        dbp = Path(tempfile.gettempdir()) / "pe3_test_rating_aggregation.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)
        return con

    def test_weighted_average_and_exclusions(self) -> None:
        con = self._db()
        try:
            # Minimal required rows.
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

            # Two tests so avg can differ from latest.
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1001, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'x')
                """,
                [date(2026, 4, 20), utc_now_naive()],
            )
            # P1: values 100 and 100 -> avg 100, latest 100 -> pct_dist 0% -> 20/20 => 100%
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1001, 101, 100.0, NULL)")
            # P2: latest 102
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2002, 1001, 102, 102.0, NULL)")

            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1000, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'y')
                """,
                [date(2026, 4, 1), utc_now_naive()],
            )
            # P2: earlier 98 -> avg becomes 100, latest is still 102 -> pct_dist = 2% -> 19/20 => 95%
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (1999, 1000, 102, 98.0, NULL)")

            upsert_weight(con, property_id=101, weight=1.0)
            upsert_weight(con, property_id=102, weight=3.0)

            # Points based on percent distance from avg.
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
                    "bands": [{"max_pct": 1.0, "points": 20}, {"max_pct": 2.0, "points": 19}, {"max_pct": None, "points": 0}],
                },
            )

            r = compute_material_rating(con, material_id=10)
            self.assertIsNotNone(r)
            self.assertAlmostEqual(float(r), 96.25, places=6)

            # Missing measurement excludes from denominator.
            con.execute("DELETE FROM measurements WHERE property_id = 102")
            r2 = compute_material_rating(con, material_id=10)
            self.assertIsNotNone(r2)
            self.assertAlmostEqual(float(r2), 100.0, places=6)

            # Weight=0 excludes property even if measurement+rule exist.
            # Restore a second measurement so avg != latest (98 and 102 => avg 100).
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3001, 1000, 102, 98.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3002, 1001, 102, 102.0, NULL)")
            upsert_weight(con, property_id=101, weight=0.0)
            r3 = compute_material_rating(con, material_id=10)
            self.assertIsNotNone(r3)
            self.assertAlmostEqual(float(r3), 95.0, places=6)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
