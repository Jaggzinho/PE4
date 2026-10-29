from __future__ import annotations

import unittest
from datetime import date

from pe3_qc_app.viz.smoothing import smooth_pchip


class TestChartSmoothing(unittest.TestCase):
    def test_duplicate_dates_no_crash(self) -> None:
        xs = [date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 2)]
        ys = [1.0, 3.0, 2.0]
        xd, yd = smooth_pchip(xs, ys, samples_per_segment=4)
        self.assertTrue(len(xd) >= 2)
        self.assertEqual(len(xd), len(yd))


if __name__ == "__main__":
    unittest.main()

