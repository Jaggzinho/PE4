from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.rating_repo import upsert_rule, upsert_weight
from pe3_qc_app.services.rating_service import fetch_rating_series
from pe3_qc_app.services.time_utils import utc_now_naive


class TestRatingSeries(unittest.TestCase):
    def _db(self):
        dbp = Path(tempfile.gettempdir()) / "pe3_test_rating_series.duckdb"
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
                "bands": [{"max_pct": 2.0, "points": 20}, {"max_pct": None, "points": 0}],
            },
        )

    def test_multiple_points_and_date_filtering(self) -> None:
        con = self._db()
        try:
            self._seed_minimal(con)

            # 3 tests in April; avg uses all-time.
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES
                    (1000, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'a'),
                    (1001, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'b'),
                    (1002, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'c')
                """,
                [
                    date(2026, 4, 1),
                    date(2026, 4, 2),
                    utc_now_naive(),
                    date(2026, 4, 10),
                    date(2026, 4, 11),
                    utc_now_naive(),
                    date(2026, 4, 20),
                    date(2026, 4, 21),
                    utc_now_naive(),
                ],
            )

            # P1 constant => always perfect for P1.
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2000, 1000, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1001, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2002, 1002, 101, 100.0, NULL)")

            # P2 values: 100, 100, 104 -> avg ~101.333, last is ~2.63% away -> rule gives 0 for P2 on last test.
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2100, 1000, 102, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2101, 1001, 102, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2102, 1002, 102, 104.0, NULL)")

            series_all = fetch_rating_series(con, material_id=10, date_from=None, date_to=None)
            self.assertEqual(len(series_all), 3)
            self.assertEqual([d for (d, _v) in series_all], [date(2026, 4, 2), date(2026, 4, 11), date(2026, 4, 21)])

            series_mid = fetch_rating_series(con, material_id=10, date_from=date(2026, 4, 5), date_to=date(2026, 4, 15))
            self.assertEqual(len(series_mid), 1)
            self.assertEqual(series_mid[0][0], date(2026, 4, 11))
        finally:
            con.close()

    def test_skips_tests_with_no_contributing_properties(self) -> None:
        con = self._db()
        try:
            self._seed_minimal(con)

            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES
                    (1000, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'a'),
                    (1001, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'b')
                """,
                [date(2026, 4, 1), date(2026, 4, 3), utc_now_naive(), date(2026, 4, 2), date(2026, 4, 4), utc_now_naive()],
            )

            # First test has only ignored property => should be skipped.
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3000, 1000, 999, 1.0, NULL)")
            # Second has contributing properties.
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3001, 1001, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3002, 1001, 102, 100.0, NULL)")

            series = fetch_rating_series(con, material_id=10, date_from=None, date_to=None)
            self.assertEqual(len(series), 1)
            self.assertEqual(series[0][0], date(2026, 4, 4))
        finally:
            con.close()

    def test_single_test_returns_one_point(self) -> None:
        con = self._db()
        try:
            self._seed_minimal(con)
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES (1000, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'a')
                """,
                [date(2026, 4, 1), date(2026, 4, 5), utc_now_naive()],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (4000, 1000, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (4001, 1000, 102, 100.0, NULL)")

            series = fetch_rating_series(con, material_id=10, date_from=None, date_to=None)
            self.assertEqual(len(series), 1)
            self.assertEqual(series[0][0], date(2026, 4, 5))
        finally:
            con.close()

    def test_excludes_excel_null_prod_date(self) -> None:
        con = self._db()
        try:
            self._seed_minimal(con)
            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES
                    (1000, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'a'),
                    (1001, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'b')
                """,
                [
                    date(2026, 4, 1),
                    date(1900, 1, 1),
                    utc_now_naive(),
                    date(2026, 4, 2),
                    date(2026, 4, 6),
                    utc_now_naive(),
                ],
            )
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3000, 1000, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3001, 1000, 102, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3002, 1001, 101, 100.0, NULL)")
            con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (3003, 1001, 102, 100.0, NULL)")

            series = fetch_rating_series(con, material_id=10, date_from=None, date_to=None)
            self.assertEqual(len(series), 1)
            self.assertEqual(series[0][0], date(2026, 4, 6))
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
