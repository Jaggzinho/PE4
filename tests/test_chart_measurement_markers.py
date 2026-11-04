from datetime import date

import pytest

from backend.app.services.charts import ChartService
from pe3_qc_app.services.chart_data import SeriesPoint


@pytest.mark.parametrize('smooth', [False, True])
def test_panel_markers_preserve_measurements_with_duplicate_dates(monkeypatch, smooth):
    import backend.app.services.charts as charts

    points = [
        SeriesPoint(date(2026, 1, 1), 10.0),
        SeriesPoint(date(2026, 1, 1), 14.0),
        SeriesPoint(date(2026, 1, 10), 20.0),
    ]
    service = ChartService()
    monkeypatch.setattr(service, '_ensure_visible', lambda *args, **kwargs: None)
    monkeypatch.setattr(charts, 'get_json', lambda *args: {})
    monkeypatch.setattr(charts, 'get_material', lambda *args, **kwargs: None)
    monkeypatch.setattr(charts, 'list_fixed_chart_properties', lambda con: [(1, 'Test', '')])
    monkeypatch.setattr(charts, 'fetch_series', lambda *args, **kwargs: points)
    panel = service.panels(
        None, subsidiary_id='tcm_ro', material_id=1, date_from=None, date_to=None,
        smooth=smooth, include_average=False, include_tolerances=False,
    )[0]
    series = panel.traces[0]
    assert series.measured_x == ['2026-01-01', '2026-01-01', '2026-01-10']
    assert series.measured_y == [10.0, 14.0, 20.0]
    if smooth:
        assert len(series.x) > len(series.measured_x)
    else:
        assert series.x == series.measured_x
        assert series.y == series.measured_y
