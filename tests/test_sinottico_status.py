from __future__ import annotations

import unittest
from datetime import date

from pe3_qc_app.services.sinottico_status import compute_status


class TestSinotticoStatus(unittest.TestCase):
    def test_none(self) -> None:
        st = compute_status(today=date(2026, 4, 17), last_request_date=None, green_days=90, yellow_days=180)
        self.assertEqual(st.level, "none")
        self.assertIsNone(st.days_since)

    def test_thresholds(self) -> None:
        today = date(2026, 4, 17)
        self.assertEqual(
            compute_status(today=today, last_request_date=date(2026, 4, 17), green_days=90, yellow_days=180).level,
            "green",
        )
        self.assertEqual(
            compute_status(today=today, last_request_date=date(2026, 1, 1), green_days=90, yellow_days=180).level,
            "yellow",
        )
        self.assertEqual(
            compute_status(today=today, last_request_date=date(2025, 1, 1), green_days=90, yellow_days=180).level,
            "red",
        )


if __name__ == "__main__":
    unittest.main()

