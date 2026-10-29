from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.services.chart_data import date_range_overlaps_bounds, fetch_date_bounds, fetch_series


class TestChartDatesUseProdDate(unittest.TestCase):
    def test_series_and_bounds_use_prod_date_only(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_chart_dates.duckdb"
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

        pid = new_id()
        con.execute(
            """
            INSERT INTO properties(property_id, name, unit, data_type, active, sort_order)
            VALUES (?, 'Durezza', NULL, 'num', TRUE, 1)
            """,
            [int(pid)],
        )

        test_id = new_id()
        req = date(2026, 1, 10)
        prod = date(2026, 1, 12)
        ana = date(2026, 1, 20)
        con.execute(
            """
            INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL, NULL, NULL)
            """,
            [int(test_id), int(mid), req, prod, ana, datetime(2026, 1, 10, 12, 0, 0)],
        )

        meas_id = new_id()
        con.execute(
            """
            INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text)
            VALUES (?, ?, ?, 50.0, NULL)
            """,
            [int(meas_id), int(test_id), int(pid)],
        )

        dmin, dmax = fetch_date_bounds(con, material_id=int(mid))
        self.assertEqual(dmin, prod)
        self.assertEqual(dmax, prod)
        self.assertFalse(date_range_overlaps_bounds(date(2026, 2, 1), date(2026, 2, 28), dmin=dmin, dmax=dmax))
        self.assertTrue(date_range_overlaps_bounds(date(2026, 1, 1), date(2026, 1, 31), dmin=dmin, dmax=dmax))

        series = fetch_series(con, material_id=int(mid), property_id=int(pid), date_from=None, date_to=None)
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0].x, prod)

        con.close()

    def test_excludes_missing_or_excel_null_prod_date(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_chart_dates_exclude_prod.duckdb"
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

        pid = new_id()
        con.execute(
            """
            INSERT INTO properties(property_id, name, unit, data_type, active, sort_order)
            VALUES (?, 'Durezza', NULL, 'num', TRUE, 1)
            """,
            [int(pid)],
        )

        # prod_date NULL -> excluded
        con.execute(
            """
            INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
            VALUES (1000, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, NULL, NULL)
            """,
            [int(mid), date(2026, 1, 1), datetime(2026, 1, 1, 12, 0, 0)],
        )
        con.execute(
            "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2000, 1000, ?, 50.0, NULL)",
            [int(pid)],
        )

        # prod_date 1900-01-01 -> excluded
        con.execute(
            """
            INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
            VALUES (1001, ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, NULL)
            """,
            [int(mid), date(2026, 1, 2), date(1900, 1, 1), datetime(2026, 1, 2, 12, 0, 0)],
        )
        con.execute(
            "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (2001, 1001, ?, 55.0, NULL)",
            [int(pid)],
        )

        dmin, dmax = fetch_date_bounds(con, material_id=int(mid))
        self.assertIsNone(dmin)
        self.assertIsNone(dmax)

        series = fetch_series(con, material_id=int(mid), property_id=int(pid), date_from=None, date_to=None)
        self.assertEqual(series, [])

        con.close()


if __name__ == "__main__":
    unittest.main()
