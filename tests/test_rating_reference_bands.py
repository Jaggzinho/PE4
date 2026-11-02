import json
from pe3_qc_app.services.rating_service import _parse_rule, _score_measurement
from pe3_qc_app.db.repos.tolerances_repo import Tolerance

def test_custom_reference_and_numeric_distance():
    tolerance = Tolerance(1, 1, 1, None, None, None, None, reference_value=70, is_custom=True)
    rule = _parse_rule(json.dumps({'type':'absolute_from_reference_bands_v1','max_points':20,'bands':[{'max_pct':5,'points':10},{'points':0}]}))
    for value, expected in [(65,50),(75,50),(75.1,0)]:
        assert _score_measurement(material_id=1, property_id=1, value=value, avg=100, rules={1:rule}, tolerances={(1,1):tolerance}) == expected

def test_percentage_reference_replaces_average():
    tolerance = Tolerance(1, 1, 1, None, None, None, None, reference_value=40, is_custom=True)
    rule = _parse_rule(json.dumps({'type':'pct_from_avg_bands_v1','max_points':20,'bands':[{'max_pct':10,'points':20},{'points':0}]}))
    assert _score_measurement(material_id=1, property_id=1, value=44, avg=100, rules={1:rule}, tolerances={(1,1):tolerance}) == 100
