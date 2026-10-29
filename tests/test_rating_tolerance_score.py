from __future__ import annotations

import pytest

from pe3_qc_app.db.repos.tolerances_repo import Tolerance
from pe3_qc_app.services.rating_service import _tolerance_score


def test_saved_tolerance_scores_both_sides_of_reference():
    tolerance = Tolerance(
        tolerance_id=1, material_id=2, property_id=3,
        warn_low=90, warn_high=110, alarm_low=80, alarm_high=150,
        reference_value=100, is_custom=True,
    )
    assert _tolerance_score(100, tolerance, 999) == 100
    assert _tolerance_score(95, tolerance, 999) == 100
    assert _tolerance_score(85, tolerance, 999) == pytest.approx(50)
    assert _tolerance_score(75, tolerance, 999) == 0
    assert _tolerance_score(130, tolerance, 999) == pytest.approx(50)
    assert _tolerance_score(150, tolerance, 999) == 0
    one_sided = Tolerance(tolerance_id=2, material_id=2, property_id=3,
                          warn_low=None, warn_high=None, alarm_low=80, alarm_high=None,
                          reference_value=100, is_custom=True)
    assert _tolerance_score(120, one_sided, 999) == 100
