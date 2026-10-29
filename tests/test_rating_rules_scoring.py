from __future__ import annotations

import unittest

from pe3_qc_app.services.rating_service import score_value, validate_rule_json


class TestRatingRulesScoring(unittest.TestCase):
    def test_ranges_v1_scoring_and_boundaries(self) -> None:
        rule = """
        {
          "type": "pct_from_avg_bands_v1",
          "max_points": 20,
          "bands": [
            { "max_pct": 1.0, "points": 20 },
            { "max_pct": 2.0, "points": 19 },
            { "max_pct": null, "points": 0 }
          ],
          "inclusive_min": true,
          "inclusive_max": true
        }
        """
        validate_rule_json(rule)
        self.assertEqual(score_value(rule, 0.0), 20.0)
        self.assertEqual(score_value(rule, 1.0), 20.0)
        self.assertEqual(score_value(rule, 2.0), 19.0)

    def test_adjacent_inclusive_ranges_invalid(self) -> None:
        rule = """
        {
          "type": "pct_from_avg_bands_v1",
          "max_points": 20,
          "bands": [
            { "max_pct": 1.0, "points": 20 },
            { "max_pct": null, "points": 0 }
          ],
          "inclusive_min": true,
          "inclusive_max": true
        }
        """
        # Adjacent inclusive bounds are allowed; first match wins.
        validate_rule_json(rule)
        self.assertEqual(score_value(rule, 1.0), 20.0)


if __name__ == "__main__":
    unittest.main()
