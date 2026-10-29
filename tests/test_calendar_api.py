from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from pe3_qc_app.auth.auth_manager import create_user
from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.repos.rating_repo import upsert_rule, upsert_weight


def _calendar_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PE3_DB_PATH", str(tmp_path / "calendar.duckdb"))
    monkeypatch.setenv("PE3_JWT_SECRET", "calendar-test-secret-at-least-32-characters")
    monkeypatch.setenv("PE3_CORS_ORIGINS", "")
    monkeypatch.setenv("PE3_SETUP_TOKEN", "setup-token")
    monkeypatch.setenv("PE3_SUBSIDIARY_ID", "tcm_ro")
    app = create_app()

    material_id = int(new_id())
    property_id = int(new_id())
    test_ids: list[int] = []
    with app.state.pe3_state.db.write() as con:
        user_id = create_user(con, username="viewer", password="pw", role_name="ReadOnly")
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'CAL-001', 'Calendar material', 'L-CAL', NULL, NULL, NULL, TRUE)
            """,
            [material_id],
        )
        con.execute(
            "INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) "
            "VALUES (?, 'Calendar property', 'MPa', 'num', TRUE, 1)",
            [property_id],
        )
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
        for index, (prod_date, value) in enumerate(
            ((date(2026, 4, 2), 100.0), (date(2026, 4, 11), 100.0), (date(2026, 4, 21), 130.0)),
            start=1,
        ):
            test_id = int(new_id())
            test_ids.append(test_id)
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
                    f"calendar-{index}",
                ],
            )
            con.execute(
                "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) "
                "VALUES (?, ?, ?, ?, NULL)",
                [int(new_id()), test_id, property_id, value],
            )
        con.execute(
            """
            INSERT INTO tolerances(
                tolerance_id, material_id, property_id, warn_low, warn_high,
                alarm_low, alarm_high, updated_at
            ) VALUES (?, ?, ?, NULL, NULL, 90.0, 120.0, ?)
            """,
            [int(new_id()), material_id, property_id, datetime(2026, 4, 1, 9, 0, 0)],
        )
    return app, test_ids


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_calendar_month_is_bounded_and_includes_test_ratings(tmp_path, monkeypatch):
    app, test_ids = _calendar_app(tmp_path, monkeypatch)
    client = TestClient(app)

    assert client.get("/api/calendar?year=2026&month=4").status_code == 401
    response = client.get("/api/calendar?year=2026&month=4", headers=_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["date_from"] == "2026-04-01"
    assert body["date_to"] == "2026-04-30"
    assert [item["test_id"] for item in body["items"]] == [str(test_id) for test_id in test_ids]
    assert [item["prod_date"] for item in body["items"]] == [
        "2026-04-02",
        "2026-04-11",
        "2026-04-21",
    ]
    assert [item["rating_percent"] for item in body["items"]] == pytest.approx([100.0, 100.0, 0.0])

    empty = client.get("/api/calendar?year=2026&month=5", headers=_headers(client))
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    upper_boundary = client.get("/api/calendar?year=9999&month=12", headers=_headers(client))
    assert upper_boundary.status_code == 200
    assert upper_boundary.json()["date_to"] == "9999-12-31"

    invalid = client.get("/api/calendar?year=2026&month=13", headers=_headers(client))
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"


def test_calendar_qc_failure_details_and_missing_test(tmp_path, monkeypatch):
    app, test_ids = _calendar_app(tmp_path, monkeypatch)
    client = TestClient(app)
    headers = _headers(client)

    response = client.get(f"/api/calendar/tests/{test_ids[-1]}/failures", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["test_id"] == str(test_ids[-1])
    assert body["material_code"] == "CAL-001"
    assert body["request_date"] == "2026-04-21"
    assert body["failures"] == [{"property_name": "Calendar property", "actual_value": "130.0"}]

    missing = client.get("/api/calendar/tests/999999999/failures", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    assert missing.json()["message"] == "Test not found"
