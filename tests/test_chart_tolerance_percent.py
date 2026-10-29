from __future__ import annotations

import unittest

from pe3_qc_app.services.chart_data import tolerance_from_avg_percent


class TestChartTolerancePercent(unittest.TestCase):
    def test_positive_avg(self) -> None:
        tol = tolerance_from_avg_percent(100.0, warn_pct=10.0, alarm_pct=20.0)
        self.assertIsNotNone(tol)
        assert tol is not None
        self.assertAlmostEqual(tol["warn_low"], 90.0)
        self.assertAlmostEqual(tol["warn_high"], 110.0)
        self.assertAlmostEqual(tol["alarm_low"], 80.0)
        self.assertAlmostEqual(tol["alarm_high"], 120.0)

    def test_negative_avg_uses_abs(self) -> None:
        tol = tolerance_from_avg_percent(-100.0, warn_pct=10.0, alarm_pct=20.0)
        self.assertIsNotNone(tol)
        assert tol is not None
        self.assertAlmostEqual(tol["warn_low"], -110.0)
        self.assertAlmostEqual(tol["warn_high"], -90.0)
        self.assertAlmostEqual(tol["alarm_low"], -120.0)
        self.assertAlmostEqual(tol["alarm_high"], -80.0)

    def test_avg_none(self) -> None:
        tol = tolerance_from_avg_percent(None, warn_pct=10.0, alarm_pct=20.0)
        self.assertIsNone(tol)

    def test_percents_unset(self) -> None:
        tol = tolerance_from_avg_percent(100.0, warn_pct=None, alarm_pct=None)
        self.assertIsNone(tol)


if __name__ == "__main__":
    unittest.main()

