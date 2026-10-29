from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas.master_data import ToleranceUpsertRequest
from backend.app.services.master_data import MasterDataService
from pe3_qc_app.auth.auth_manager import create_user
from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.repos.rating_repo import upsert_rule, upsert_weight
from pe3_qc_app.db.repos.tolerances_repo import ensure_material_tolerance
from pe3_qc_app.services.rating_service import compute_average_ratings_for_materials, compute_material_rating


def _app_with_ratings(tmp_path, monkeypatch, *, configured: bool = True):
    monkeypatch.setenv("PE3_DB_PATH", str(tmp_path / "ratings.duckdb"))
    monkeypatch.setenv("PE3_JWT_SECRET", "ratings-test-secret-at-least-32-characters")
    monkeypatch.setenv("PE3_CORS_ORIGINS", "")
    monkeypatch.setenv("PE3_SETUP_TOKEN", "setup-token")
    monkeypatch.setenv("PE3_SUBSIDIARY_ID", "tcm_ro")
    app = create_app()

    material_id = int(new_id())
    hidden_material_id = int(new_id())
    property_id = int(new_id())
    with app.state.pe3_state.db.write() as con:
        user_id = create_user(con, username="viewer", password="pw", role_name="ReadOnly")
        con.execute(
            "INSERT INTO settings(key, value_json) VALUES ('visible_material_codes', '[]') "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
        )
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'VISIBLE', 'Visible material', NULL, NULL, NULL, NULL, TRUE),
                   (?, 'HIDDEN', 'Hidden material', NULL, NULL, NULL, NULL, TRUE)
            """,
            [material_id, hidden_material_id],
        )
        con.execute(
            """
            INSERT INTO sinottico_items(item_id, machine_code, excel_label, excel_code, description, material_id, sort_order, active)
            VALUES (?, 'MC-R', NULL, 'RATING', 'Rating row', ?, 1, TRUE)
            """,
            [int(new_id()), material_id],
        )
        con.execute(
            "INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) "
            "VALUES (?, 'Rating property', NULL, 'num', TRUE, 1)",
            [property_id],
        )
        for index, (prod_date, value) in enumerate(
            ((date(2026, 4, 2), 100.0), (date(2026, 4, 11), 100.0), (date(2026, 4, 21), 130.0)),
            start=1,
        ):
            test_id = int(new_id())
            con.execute(
                """
                INSERT INTO tests(
                    test_id, material_id, request_date, prod_date, analysis_date, notes,
                    created_by, created_at, deleted_at, external_source, external_row_key
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, NULL, 'Manual', ?)
                """,
                [
                    test_id,
                    material_id,
                    prod_date,
                    prod_date,
                    user_id,
                    datetime(2026, 4, index, 10, 0, 0),
                    f"rating-{index}",
                ],
            )
            con.execute(
                "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) "
                "VALUES (?, ?, ?, ?, NULL)",
                [int(new_id()), test_id, property_id, value],
            )
        if configured:
            upsert_weight(con, property_id=property_id, weight=1.0)
            upsert_rule(
                con,
                property_id=property_id,
                rule_json={
                    "type": "pct_from_avg_bands_v1",
                    "max_points": 20,
                    "bands": [
                        {"max_pct": 10.0, "points": 20},
                        {"max_pct": None, "points": 0},
                    ],
                },
            )
    return app, material_id, hidden_material_id


def _viewer_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ratings_overview_visibility_dates_and_summary(tmp_path, monkeypatch):
    app, material_id, hidden_material_id = _app_with_ratings(tmp_path, monkeypatch)
    client = TestClient(app)

    assert client.get(f"/api/ratings?material_id={material_id}").status_code == 401
    headers = _viewer_headers(client)
    response = client.get(f"/api/ratings?material_id={material_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["date_min"] == "2026-04-02"
    assert body["date_max"] == "2026-04-21"
    assert body["date_from"] == "2026-04-02"
    assert body["date_to"] == "2026-04-21"
    assert [point["rating_percent"] for point in body["points"]] == pytest.approx([100.0, 100.0, 0.0])
    assert body["latest_rating"] == pytest.approx(0.0)
    assert body["average_rating"] == pytest.approx(200.0 / 3.0)

    filtered = client.get(
        f"/api/ratings?material_id={material_id}&date_from=2026-04-10&date_to=2026-04-21",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [point["date"] for point in filtered.json()["points"]] == ["2026-04-11", "2026-04-21"]
    assert filtered.json()["average_rating"] == pytest.approx(50.0)

    invalid = client.get(
        f"/api/ratings?material_id={material_id}&date_from=2026-05-01&date_to=2026-04-01",
        headers=headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "bad_request"
    assert invalid.json()["message"] == "date_from must be on or before date_to"

    partial_invalid = client.get(
        f"/api/ratings?material_id={material_id}&date_from=2026-05-01",
        headers=headers,
    )
    assert partial_invalid.status_code == 400
    assert partial_invalid.json()["code"] == "bad_request"

    hidden = client.get(f"/api/ratings?material_id={hidden_material_id}", headers=headers)
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "not_found"


def test_ratings_overview_reports_missing_configuration(tmp_path, monkeypatch):
    app, material_id, _hidden_material_id = _app_with_ratings(tmp_path, monkeypatch, configured=False)
    client = TestClient(app)

    response = client.get(f"/api/ratings?material_id={material_id}", headers=_viewer_headers(client))

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["points"] == []
    assert response.json()["latest_rating"] is None
    assert response.json()["average_rating"] is None


def test_custom_material_tolerance_recalculates_all_rating_views(tmp_path, monkeypatch):
    app, material_id, _ = _app_with_ratings(tmp_path, monkeypatch)
    client = TestClient(app)
    headers = _viewer_headers(client)
    property_id = None
    with app.state.pe3_state.db.serialized() as con:
        property_id = int(con.execute("SELECT property_id FROM properties WHERE name='Rating property'").fetchone()[0])
        saved = MasterDataService().save_tolerance(con, tolerance_id=None, payload=ToleranceUpsertRequest(
            material_id=material_id, property_id=property_id, reference_value=100,
            warn_low_input=90, warn_high_input=110, alarm_low_input=80, alarm_high_input=150,
        ))
    response = client.get(f"/api/ratings?material_id={material_id}", headers=headers)
    assert response.status_code == 200
    assert [point["rating_percent"] for point in response.json()["points"]] == pytest.approx([100, 100, 50])
    assert response.json()["latest_rating"] == pytest.approx(50)
    with app.state.pe3_state.db.connect() as con:
        assert compute_material_rating(con, material_id=material_id) == pytest.approx(50)
        assert compute_average_ratings_for_materials(con, material_ids=[material_id])[material_id] == pytest.approx(250 / 3)
    with app.state.pe3_state.db.serialized() as con:
        MasterDataService().save_tolerance(con, tolerance_id=saved.tolerance_id, payload=ToleranceUpsertRequest(
            material_id=material_id, property_id=property_id, reference_value=100,
            warn_low_input=95, warn_high_input=105, alarm_low_input=90, alarm_high_input=120,
        ))
    updated = client.get(f"/api/ratings?material_id={material_id}", headers=headers)
    assert updated.status_code == 200
    assert updated.json()["latest_rating"] == pytest.approx(0)
    with app.state.pe3_state.db.serialized() as con:
        MasterDataService().delete_tolerance(con, tolerance_id=saved.tolerance_id)
    fallback = client.get(f"/api/ratings?material_id={material_id}", headers=headers)
    assert [point["rating_percent"] for point in fallback.json()["points"]] == pytest.approx([100, 100, 0])


def test_saved_tolerance_with_weight_can_rate_without_fallback_rule(tmp_path, monkeypatch):
    app, material_id, _ = _app_with_ratings(tmp_path, monkeypatch, configured=False)
    with app.state.pe3_state.db.serialized() as con:
        property_id = int(con.execute("SELECT property_id FROM properties WHERE name='Rating property'").fetchone()[0])
        upsert_weight(con, property_id=property_id, weight=1)
        MasterDataService().save_tolerance(con, tolerance_id=None, payload=ToleranceUpsertRequest(
            material_id=material_id, property_id=property_id, reference_value=100,
            warn_high_input=110, alarm_high_input=150, alarm_low_input=80,
        ))
    client = TestClient(app)
    response = client.get(f"/api/ratings?material_id={material_id}", headers=_viewer_headers(client))
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert [point["rating_percent"] for point in response.json()["points"]] == pytest.approx([100, 100, 50])


def test_generated_chart_fallback_does_not_replace_rating_rule(tmp_path, monkeypatch):
    app, material_id, _ = _app_with_ratings(tmp_path, monkeypatch)
    with app.state.pe3_state.db.serialized() as con:
        property_id = int(con.execute("SELECT property_id FROM properties WHERE name='Rating property'").fetchone()[0])
        ensure_material_tolerance(con, material_id=material_id, property_id=property_id,
                                  warn_low=None, warn_high=None, alarm_low=80, alarm_high=150)
    client = TestClient(app)
    response = client.get(f"/api/ratings?material_id={material_id}", headers=_viewer_headers(client))
    assert response.status_code == 200
    assert [point["rating_percent"] for point in response.json()["points"]] == pytest.approx([100, 100, 0])
