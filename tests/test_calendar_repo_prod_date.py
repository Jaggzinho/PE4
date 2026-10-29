from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.calendar_repo import list_tests_by_prod_date_range
from pe3_qc_app.services.time_utils import utc_now_naive


class TestCalendarRepoProdDate(unittest.TestCase):
    def test_list_tests_by_prod_date_range_excludes_null_and_excel_null(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_calendar_prod_date.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)
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
                VALUES (10, 'MAT', 'M', 'L001', NULL, NULL, NULL, TRUE)
                """
            )

            con.execute(
                """
                INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
                VALUES
                    (1000, 10, ?, NULL, NULL, NULL, 1, ?, NULL, 'Manual', 'a'),
                    (1001, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'b'),
                    (1002, 10, ?, ?, NULL, NULL, 1, ?, NULL, 'Manual', 'c')
                """,
                [
                    date(2026, 4, 1),
                    utc_now_naive(),
                    date(2026, 4, 2),
                    date(1900, 1, 1),
                    utc_now_naive(),
                    date(2026, 4, 3),
                    date(2026, 4, 10),
                    utc_now_naive(),
                ],
            )

            rows = list_tests_by_prod_date_range(con, date_from=date(2026, 4, 1), date_to=date(2026, 4, 30))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].test_id, 1002)
            self.assertEqual(rows[0].prod_date, date(2026, 4, 10))
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()

