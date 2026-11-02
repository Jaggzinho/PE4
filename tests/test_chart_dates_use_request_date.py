from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.services.chart_data import date_range_overlaps_bounds, fetch_avg, fetch_date_bounds, fetch_series


class TestChartDatesUseRequestDate(unittest.TestCase):
    def test_series_and_bounds_use_request_date_only(self) -> None:
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
        self.assertEqual(dmin, req)
        self.assertEqual(dmax, req)
        self.assertFalse(date_range_overlaps_bounds(date(2026, 2, 1), date(2026, 2, 28), dmin=dmin, dmax=dmax))
        self.assertTrue(date_range_overlaps_bounds(date(2026, 1, 1), date(2026, 1, 31), dmin=dmin, dmax=dmax))

        series = fetch_series(con, material_id=int(mid), property_id=int(pid), date_from=None, date_to=None)
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0].x, req)

        con.close()

    def test_includes_missing_or_excel_null_prod_date(self) -> None:
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

        # prod_date NULL -> included
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

        # prod_date 1900-01-01 -> included
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
        self.assertEqual(dmin, date(2026, 1, 1))
        self.assertEqual(dmax, date(2026, 1, 2))

        series = fetch_series(con, material_id=int(mid), property_id=int(pid), date_from=None, date_to=None)
        self.assertEqual([p.x for p in series], [date(2026, 1, 1), date(2026, 1, 2)])
        self.assertEqual([p.y for p in series], [50.0, 55.0])

        con.close()


if __name__ == "__main__":
    unittest.main()


def test_request_date_boundaries_same_day_and_exclusions(tmp_path):
    with duckdb.connect(str(tmp_path / "charts.duckdb")) as con:
        con.execute("CREATE TABLE tests(test_id BIGINT, material_id BIGINT, request_date DATE, prod_date DATE, deleted_at TIMESTAMP)")
        con.execute("CREATE TABLE measurements(measurement_id BIGINT, test_id BIGINT, property_id BIGINT, value_num DOUBLE, value_text VARCHAR)")
        con.execute("""
            INSERT INTO tests VALUES
              (2, 1, '2026-04-10', NULL, NULL),
              (1, 1, '2026-04-10', '1900-01-01', NULL),
              (3, 1, '2026-04-11', '2026-03-01', NULL),
              (4, 1, NULL, '2026-04-10', NULL),
              (5, 1, '1900-01-01', '2026-04-10', NULL),
              (6, 1, '2026-04-12', NULL, CURRENT_TIMESTAMP),
              (7, 2, '2026-04-13', NULL, NULL)
        """)
        con.execute("INSERT INTO measurements SELECT test_id, test_id, 1, test_id * 10, NULL FROM tests")
        points = fetch_series(con, material_id=1, property_id=1, date_from=date(2026, 4, 10), date_to=date(2026, 4, 10))
        assert [p.y for p in points] == [10.0, 20.0]
        assert [p.x for p in points] == [date(2026, 4, 10)] * 2
        assert fetch_avg(con, material_id=1, property_id=1, date_from=date(2026, 4, 10), date_to=date(2026, 4, 10)) == 15.0
        assert fetch_date_bounds(con, material_id=1) == (date(2026, 4, 10), date(2026, 4, 11))
        assert len(fetch_series(con, material_id=1, property_id=1, date_from=None, date_to=None)) == 3
