from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.rating_repo import upsert_rule, upsert_weight
from pe3_qc_app.services.test_rating_service import compute_test_ratings
from pe3_qc_app.services.time_utils import utc_now_naive


class TestTestRatingService(unittest.TestCase):
    def _db(self):
        dbp = Path(tempfile.gettempdir()) / "pe3_test_test_rating_service.duckdb"
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

    def test_compute_test_ratings_returns_mapping(self) -> None:
        con = self._db()
        try:
            self._seed_minimal(con)
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES
                    (1000, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'a'),
                    (1001, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'b')
                """,
                [date(2026, 4, 1), utc_now_naive(), date(2026, 4, 2), utc_now_naive()],
            )

            # Make averages stable.
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2000, 1000, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1000, 102, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2002, 1001, 101, 100.0, NULL)")
            # Second test has P2 far from avg => bad rating.
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2003, 1001, 102, 200.0, NULL)")

            res = compute_test_ratings(con, tests=[(1000, 10), (1001, 10)])
            self.assertIn(1000, res)
            self.assertIn(1001, res)
            self.assertGreaterEqual(float(res[1000]), float(res[1001]))
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()

