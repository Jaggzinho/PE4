from __future__ import annotations

import unittest

from pe3_qc_app.services.chart_data import tolerance_from_avg_abs


class TestChartToleranceAbs(unittest.TestCase):
    def test_alarm_band(self) -> None:
        tol = tolerance_from_avg_abs(50.0, alarm_delta=2.0)
        self.assertIsNotNone(tol)
        assert tol is not None
        self.assertIsNone(tol["warn_low"])
        self.assertIsNone(tol["warn_high"])
        self.assertAlmostEqual(tol["alarm_low"], 48.0)
        self.assertAlmostEqual(tol["alarm_high"], 52.0)

    def test_avg_none(self) -> None:
        tol = tolerance_from_avg_abs(None, alarm_delta=2.0)
        self.assertIsNone(tol)


if __name__ == "__main__":
    unittest.main()

