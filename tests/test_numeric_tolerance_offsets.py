from backend.app.schemas.master_data import ToleranceUpsertRequest
from backend.app.services.master_data import _resolved_tolerance, ToleranceValidationError
import pytest

def test_numeric_offsets():
    payload = ToleranceUpsertRequest(property_id=1, reference_value=70, warn_low_input=2, warn_high_input=2, alarm_low_input=3, alarm_high_input=3,
                                    warn_low_mode="offset", warn_high_mode="offset", alarm_low_mode="offset", alarm_high_mode="offset")
    effective, inputs = _resolved_tolerance(payload)
    assert effective == dict(warn_low=68, warn_high=72, alarm_low=67, alarm_high=73)
    assert inputs['warn_low_input'] == 2

def test_negative_numeric_offset_rejected():
    with pytest.raises(ToleranceValidationError, match='nonnegative'):
        _resolved_tolerance(ToleranceUpsertRequest(property_id=1, reference_value=70, warn_low_input=-2, warn_low_mode="offset"))


def test_numeric_offset_requires_reference():
    with pytest.raises(ToleranceValidationError, match='reference is required'):
        _resolved_tolerance(ToleranceUpsertRequest(property_id=1, warn_low_input=2, warn_low_mode="offset"))


def test_numeric_offset_supports_zero_reference():
    effective, _ = _resolved_tolerance(ToleranceUpsertRequest(
        property_id=1, reference_value=0, warn_low_input=2, warn_high_input=2,
        warn_low_mode="offset", warn_high_mode="offset",
    ))
    assert (effective['warn_low'], effective['warn_high']) == (-2, 2)


def test_absolute_limits_can_be_negative():
    effective, _ = _resolved_tolerance(ToleranceUpsertRequest(
        property_id=1, reference_value=0, warn_low_input=-2, warn_high_input=2,
    ))
    assert (effective['warn_low'], effective['warn_high']) == (-2, 2)
