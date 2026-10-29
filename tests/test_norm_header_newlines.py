from __future__ import annotations

import unittest

from pe3_qc_app.importer.xlsm_utils import norm_header


class TestNormHeaderNewlines(unittest.TestCase):
    def test_collapses_newlines(self) -> None:
        self.assertEqual(norm_header("LOTTO\nISO"), "lotto iso")
        self.assertEqual(norm_header("DESCRIZIONE\nADD1"), "descrizione add1")


if __name__ == "__main__":
    unittest.main()

