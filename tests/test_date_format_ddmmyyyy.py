from __future__ import annotations

import unittest
from datetime import date

from pe3_qc_app.services.date_format import format_date


class TestDateFormatDDMMYYYY(unittest.TestCase):
    def test_format_date(self) -> None:
        self.assertEqual(format_date(date(2026, 1, 2)), "02/01/2026")

    def test_format_none(self) -> None:
        self.assertEqual(format_date(None, empty="—"), "—")


if __name__ == "__main__":
    unittest.main()

