"""Independent distance bands no longer override custom limits or the 20% fallback."""

import json

import pytest

from pe3_qc_app.db.repos.tolerances_repo import Tolerance
from pe3_qc_app.services.rating_service import _parse_rule, _score_measurement, _tolerance_score


def _rule(**overrides):
    return _parse_rule(json.dumps({
        "type": "custom_tolerance_points_v1", "max_points": 10,
        "warn_low_points": 10, "warn_high_points": 10,
        "alarm_low_points": 10, "alarm_high_points": 10, **overrides,
    }))


@pytest.mark.parametrize("value,expected", [(79.99, 0), (80, 100), (85, 100), (90, 100), (100, 100), (110, 100), (130, 100), (150, 100), (150.01, 0)])
def test_equal_points_award_full_score_in_entire_inclusive_alarm_band(value, expected):
    tolerance = Tolerance(1, 1, 1, 90, 110, 80, 150, reference_value=100, is_custom=True)
    assert _tolerance_score(value, tolerance, 999, _rule()) == expected


@pytest.mark.parametrize("value,expected", [(80, 20), (85, 50), (90, 80), (95, 90), (100, 100), (105, 80), (110, 60), (130, 50), (150, 40)])
def test_asymmetric_points_interpolate_from_reference_through_saved_limits(value, expected):
    tolerance = Tolerance(1, 1, 1, 90, 110, 80, 150, reference_value=100, is_custom=True)
    rule = _rule(warn_low_points=8, warn_high_points=6, alarm_low_points=2, alarm_high_points=4)
    assert _tolerance_score(value, tolerance, 999, rule) == pytest.approx(expected)


@pytest.mark.parametrize("average,value,expected", [
    (100, 80, 100), (100, 120, 100), (100, 79.99, 0), (100, 120.01, 0),
    (-100, -120, 100), (-100, -80, 100), (-100, -120.01, 0), (-100, -79.99, 0),
    (0, 0, 100), (0, 0.001, 0), (None, 1, None), (float("nan"), 1, None),
    (100, float("inf"), None),
])
def test_fallback_is_fixed_twenty_percent_even_for_legacy_absolute_rules(average, value, expected):
    legacy = _parse_rule(json.dumps({"type": "absolute_from_reference_bands_v1", "max_points": 20, "bands": [{"max_pct": 1, "points": 7}, {"points": 0}]}))
    assert _score_measurement(material_id=1, property_id=1, value=value, avg=average, rules={1: legacy}, tolerances={}) == expected


def test_reference_without_limits_uses_average_fallback_and_rule_is_optional():
    reference_only = Tolerance(1, 1, 1, None, None, None, None, reference_value=70, is_custom=True)
    assert _score_measurement(material_id=1, property_id=1, value=100, avg=100, rules={}, tolerances={(1, 1): reference_only}) == 100


def test_missing_reference_and_one_sided_limits():
    tolerance = Tolerance(1, 1, 1, None, 110, None, 150, is_custom=True)
    assert _tolerance_score(130, tolerance, 100, _rule()) == 100
    assert _tolerance_score(1000, tolerance, 100, _rule()) == 0
    assert _tolerance_score(-1000, tolerance, 100, _rule()) == 100
    asymmetric = Tolerance(1, 1, 1, 90, 110, 80, 200, is_custom=True)
    assert _tolerance_score(95, asymmetric, 999, _rule()) == 100


def test_coincident_alarm_and_warning_uses_alarm_points():
    tolerance = Tolerance(1, 1, 1, 80, 120, 80, 120, reference_value=100, is_custom=True)
    assert _tolerance_score(80, tolerance, 100, _rule(warn_low_points=8, alarm_low_points=3)) == 30


@pytest.mark.parametrize("overrides", [
    {"max_points": 0}, {"max_points": float("inf")}, {"max_points": {}},
    {"alarm_low_points": -1}, {"warn_high_points": 11},
    {"warn_low_points": None}, {"alarm_high_points": float("nan")},
    {"alarm_high_points": []}, {"bands": []},
])
def test_point_rules_reject_invalid_values(overrides):
    with pytest.raises(ValueError):
        _rule(**overrides)
