from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.tolerances_repo import ensure_material_tolerance
from pe3_qc_app.services.chart_data import (
    baseline_from_tolerance,
    durezza_tol_from_material_description,
    tolerance_from_avg_percent,
)


class TestChartToleranceFreezeHelpers(unittest.TestCase):
    def test_durezza_description_detects_70_80_90(self) -> None:
        self.assertIsNone(durezza_tol_from_material_description(None))
        self.assertIsNone(durezza_tol_from_material_description(""))
        self.assertIsNone(durezza_tol_from_material_description("foo 180 bar"))
        self.assertIsNone(durezza_tol_from_material_description("foo 80% bar"))
        self.assertIsNone(durezza_tol_from_material_description("foo 80 % bar"))

        tol70 = durezza_tol_from_material_description("MAT something 70 shore")
        self.assertIsNotNone(tol70)
        assert tol70 is not None
        self.assertAlmostEqual(tol70["alarm_low"], 68.0)
        self.assertAlmostEqual(tol70["alarm_high"], 72.0)

        tol80 = durezza_tol_from_material_description("80 ShA")
        assert tol80 is not None
        self.assertAlmostEqual(tol80["alarm_low"], 78.0)
        self.assertAlmostEqual(tol80["alarm_high"], 82.0)

        tol = durezza_tol_from_material_description("70 80 90")
        assert tol is not None
        self.assertAlmostEqual(tol["alarm_low"], 88.0)
        self.assertAlmostEqual(tol["alarm_high"], 92.0)

    def test_baseline_prefers_alarm_midpoint(self) -> None:
        self.assertIsNone(baseline_from_tolerance(None, None))
        self.assertAlmostEqual(baseline_from_tolerance(None, 12.5) or 0.0, 12.5)

        tol = {"warn_low": 90.0, "warn_high": 110.0, "alarm_low": 80.0, "alarm_high": 120.0}
        self.assertAlmostEqual(baseline_from_tolerance(tol, 100.0) or 0.0, 100.0)

        tol2 = {"warn_low": 90.0, "warn_high": 110.0, "alarm_low": None, "alarm_high": None}
        self.assertAlmostEqual(baseline_from_tolerance(tol2, 123.0) or 0.0, 100.0)


class TestToleranceFreezeIntegration(unittest.TestCase):
    def test_ensure_material_tolerance_inserts_once(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_tol_freeze.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

        mid = int(new_id())
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'MAT001', 'Material 001', NULL, NULL, NULL, NULL, TRUE)
            """,
            [mid],
        )

        pid = int(new_id())
        con.execute(
            """
            INSERT INTO properties(property_id, name, unit, data_type, active, sort_order)
            VALUES (?, 'Abrasione', NULL, 'num', TRUE, 1)
            """,
            [pid],
        )

        computed = tolerance_from_avg_percent(100.0, warn_pct=10.0, alarm_pct=20.0)
        assert computed is not None
        first = ensure_material_tolerance(con, material_id=mid, property_id=pid, **computed)
        self.assertAlmostEqual(first["warn_low"], 90.0)
        self.assertAlmostEqual(first["warn_high"], 110.0)
        self.assertAlmostEqual(first["alarm_low"], 80.0)
        self.assertAlmostEqual(first["alarm_high"], 120.0)

        computed2 = tolerance_from_avg_percent(200.0, warn_pct=10.0, alarm_pct=20.0)
        assert computed2 is not None
        second = ensure_material_tolerance(con, material_id=mid, property_id=pid, **computed2)
        # Should stay frozen on the first insert
        self.assertAlmostEqual(second["alarm_low"], 80.0)
        self.assertAlmostEqual(second["alarm_high"], 120.0)

        con.close()


if __name__ == "__main__":
    unittest.main()

