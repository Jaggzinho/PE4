from __future__ import annotations

from datetime import date, datetime
import os
from pathlib import Path
import time

import duckdb
from fastapi.testclient import TestClient

from pe3_qc_app.auth.auth_manager import create_user
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.ids import new_id
from backend.app.main import create_app


def _seed_db(db_path: str) -> None:
    con = duckdb.connect(db_path)
    try:
        apply_migrations(con)
        # For web visibility: empty whitelist => use SINOTTICO-linked materials as visible.
        con.execute(
            "INSERT INTO settings(key, value_json) VALUES ('visible_material_codes', '[]') ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
        )
        mid = int(new_id())
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'MAT-001', 'Material test', 'L-1', 'Lastrina', NULL, NULL, TRUE)
            """,
            [mid],
        )
        con.execute(
            """
            INSERT INTO sinottico_items(item_id, machine_code, excel_label, excel_code, description, material_id, sort_order, active)
            VALUES (1, 'MC-01', NULL, 'EX-01', 'Row test', ?, 1, TRUE)
            """,
            [mid],
        )

        # Properties required by list_fixed_chart_properties
        props = [
            ("Lacerazione B", "N/mm"),
            ("Lacerazione C", "N/mm"),
            ("Abrasione", "mg"),
            ("Durezza", "ShA"),
            ("Carico di rottura", "MPa"),
            ("Allungamento", "%"),
        ]
        for i, (name, unit) in enumerate(props, start=10):
            con.execute(
                "INSERT INTO properties(property_id, name, unit, data_type, active, sort_order) VALUES (?, ?, ?, 'num', TRUE, ?)",
                [i, name, unit, i],
            )

        uid = create_user(con, username="admin", password="pw", role_name="Admin")
        create_user(con, username="viewer", password="pw", role_name="ReadOnly")
        tid = int(new_id())
        con.execute(
            """
            INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, notes, created_by, created_at, deleted_at, external_source, external_row_key)
            VALUES (?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL, NULL)
            """,
            [tid, mid, date(2026, 1, 2), uid, datetime(2026, 1, 2, 10, 0, 0)],
        )
        for pid in range(10, 16):
            con.execute(
                "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (?, ?, ?, ?, NULL)",
                [int(new_id()), tid, pid, float(pid)],
            )
    finally:
        con.close()


def _client(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    _seed_db(db_path)
    os.environ["PE3_DB_PATH"] = db_path
    os.environ["PE3_JWT_SECRET"] = "test-secret"
    os.environ["PE3_CORS_ORIGINS"] = ""
    os.environ["PE3_SETUP_TOKEN"] = "setup-token"
    os.environ["PE3_SUBSIDIARY_ID"] = "tcm_ro"
    app = create_app()
    return TestClient(app)


def _client_empty(tmp_path):
    db_path = str(tmp_path / "empty.duckdb")
    con = duckdb.connect(db_path)
    try:
        apply_migrations(con)
    finally:
        con.close()
    os.environ["PE3_DB_PATH"] = db_path
    os.environ["PE3_JWT_SECRET"] = "test-secret"
    os.environ["PE3_CORS_ORIGINS"] = ""
    os.environ["PE3_SETUP_TOKEN"] = "setup-token"
    os.environ["PE3_SUBSIDIARY_ID"] = "tcm_ro"
    app = create_app()
    return TestClient(app)


def test_login_me_and_sinottico(tmp_path):
    client = _client(tmp_path)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"

    r = client.get("/api/sinottico", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    assert rows[0]["machine_code"] == "MC-01"


def test_material_search_and_charts(tmp_path):
    client = _client(tmp_path)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    token = r.json()["access_token"]

    r = client.get("/api/materials?q=mat-001", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    mats = r.json()
    assert len(mats) == 1
    mid = mats[0]["material_id"]

    r = client.get(f"/api/charts?material_id={mid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["material_id"] == mid
    assert len(data["traces"]) >= 1
    assert all(len(t["x"]) == len(t["y"]) for t in data["traces"])

    r = client.get("/api/charts/config", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    cfg = r.json()
    assert "tolerance_pct" in cfg
    assert len(cfg["fixed_properties"]) == 6

    r = client.get(f"/api/charts/panels?material_id={mid}&avg=true&tolerances=true&smooth=true", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    panels = r.json()
    assert panels["material_id"] == mid
    assert len(panels["panels"]) == 6
    assert all("traces" in p for p in panels["panels"])


def test_material_search_includes_imported_component_defaults(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    try:
        material_id = int(con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()[0])
        type_id = int(new_id())
        component_id = int(new_id())
        con.execute(
            "INSERT INTO component_types(type_id, name, slot_key, active) VALUES (?, 'ISOCIANATO', 'ISO', TRUE)",
            [type_id],
        )
        con.execute(
            "INSERT INTO components(component_id, type_id, code, description, active) VALUES (?, ?, 'ISO-DEFAULT', 'Imported ISO', TRUE)",
            [component_id, type_id],
        )
        con.execute(
            "INSERT INTO material_component_defaults(material_id, slot_key, component_id) VALUES (?, 'ISO', ?)",
            [material_id, component_id],
        )
    finally:
        con.close()

    response = client.get("/api/materials?q=MAT-001", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["component_defaults"]["ISO"] == {
        "code": "ISO-DEFAULT",
        "desc": "Imported ISO",
    }


def test_charts_reject_invalid_iso_date_with_error_contract(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    material = client.get("/api/materials?q=MAT-001", headers=headers).json()[0]

    response = client.get(
        f"/api/charts?material_id={material['material_id']}&date_from=not-a-date",
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["message"] == "Request validation failed"


def test_setup_flow_requires_token_and_no_users(tmp_path):
    client = _client_empty(tmp_path)

    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json()["needs_setup"] is True

    r = client.post("/api/setup/first-admin", json={"username": "admin", "password": "pw", "password2": "pw"})
    assert r.status_code == 403

    r = client.post(
        "/api/setup/first-admin",
        headers={"X-PE3-SETUP-TOKEN": "setup-token"},
        json={"username": "admin", "password": "pw", "password2": "pw"},
    )
    assert r.status_code == 204

    r = client.get("/api/setup/status")
    assert r.status_code == 200
    assert r.json()["needs_setup"] is False

    # Setup should now be blocked
    r = client.post(
        "/api/setup/first-admin",
        headers={"X-PE3-SETUP-TOKEN": "setup-token"},
        json={"username": "x", "password": "pw", "password2": "pw"},
    )
    assert r.status_code == 409

    # And login should work
    r = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert r.status_code == 200


def test_settings_charts_tolerance_pct_roundtrip(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/settings/charts-tolerance-pct", headers=h)
    assert r.status_code == 200

    r = client.put("/api/settings/charts-tolerance-pct", headers=h, json={"warn_pct": 11.0, "alarm_pct": 22.0})
    assert r.status_code == 200
    assert r.json()["warn_pct"] == 11.0


def _auth(client: TestClient) -> str:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_lots_crud(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/materials?q=MAT-001", headers=h)
    assert r.status_code == 200
    mid = r.json()[0]["material_id"]

    r = client.get("/api/lots", headers=h)
    assert r.status_code == 200
    before = r.json()["items"]

    payload = {
        "material_id": mid,
        "request_date": "2026-02-01",
        "prod_date": None,
        "analysis_date": "2026-02-03",
        "components": {
            "ISO": {"code": "ISO-1", "desc": "ISO desc", "lot": "L-ISO"},
            "ADD3": {"code": "ADD3-1", "desc": "Additive 3", "lot": "L-ADD3"},
        },
        "qc": {"durezza": "70.5"},
    }
    r = client.post("/api/lots", json=payload, headers=h)
    assert r.status_code == 200
    created = r.json()
    assert created["material_id"] == mid
    assert created["qc"]["durezza"] == "70.5"
    assert created["components"]["ADD3"] == {
        "code": "ADD3-1",
        "desc": "Additive 3",
        "lot": "L-ADD3",
    }

    test_id = created["test_id"]
    payload2 = {**payload, "qc": {"durezza": "71.0", "abrasione": "3.2"}}
    r = client.put(f"/api/lots/{test_id}", json=payload2, headers=h)
    assert r.status_code == 200
    updated = r.json()
    assert updated["qc"]["durezza"] == "71.0"

    r = client.delete(f"/api/lots/{test_id}", headers=h)
    assert r.status_code == 204

    r = client.get("/api/lots", headers=h)
    assert r.status_code == 200
    after = r.json()["items"]
    assert len(after) == len(before)


def test_lots_rbac_blocks_readonly(tmp_path):
    client = _client(tmp_path)
    r = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/materials?q=MAT-001", headers=h)
    assert r.status_code == 200
    mid = r.json()[0]["material_id"]

    r = client.post("/api/lots", json={"material_id": mid}, headers=h)
    assert r.status_code == 403


def test_sinottico_queue_email_preview_and_finalize(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    # Enqueue the seeded sinottico item_id=1
    r = client.post("/api/sinottico/queue/items/1", headers=h)
    assert r.status_code == 204

    r = client.get("/api/sinottico/queue", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.post("/api/sinottico/queue/email-preview", headers=h)
    assert r.status_code == 200
    draft = r.json()
    assert "subject" in draft and isinstance(draft["subject"], str)

    r = client.post("/api/sinottico/queue/email.eml", headers=h)
    assert r.status_code == 200
    assert "message/rfc822" in (r.headers.get("content-type") or "")

    r = client.post("/api/sinottico/queue/finalize", headers=h)
    assert r.status_code == 200
    out = r.json()
    assert out["sample_requests_logged"] >= 1

    r = client.get("/api/sinottico/queue", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_sinottico_email_preview_rejects_empty_queue(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)

    response = client.post(
        "/api/sinottico/queue/email-preview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert response.json()["message"] == "Queue is empty"


def test_import_xlsm_rejects_bad_extension(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/import/xlsm", headers=h, files={"file": ("bad.txt", b"nope", "text/plain")})
    assert r.status_code == 400


def test_import_xlsm_happy_path_with_repo_workbook(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    repo_root = Path(__file__).resolve().parents[1]
    wb_path = repo_root / "CONTROLLO LASTRINE TCM RO REV2.xlsm"
    if not wb_path.exists():
        # Optional: in some environments the sample workbook may be absent.
        return

    data = wb_path.read_bytes()
    r = client.post(
        "/api/import/xlsm",
        headers=h,
        files={"file": (wb_path.name, data, "application/vnd.ms-excel.sheet.macroEnabled.12")},
    )
    assert r.status_code == 200
    body = r.json()
    assert "result" in body
    assert body["result"]["materials"] >= 0


def test_import_job_reports_progress_and_result(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    workbook = Path(__file__).resolve().parents[1] / "CONTROLLO LASTRINE TCM RO REV2.xlsm"
    if not workbook.exists():
        return

    response = client.post(
        "/api/imports",
        headers=headers,
        files={
            "file": (
                workbook.name,
                workbook.read_bytes(),
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            )
        },
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status_response = client.get(f"/api/jobs/{job_id}", headers=headers)
        assert status_response.status_code == 200
        job = status_response.json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("import job did not finish")

    assert job["status"] == "succeeded"
    assert job["progress"] == 100
    assert job["result"]["materials"] >= 0
    assert job["messages"]

    # Re-importing the same workbook must use the importer's duplicate policy,
    # not fail because the work was moved to the job queue.
    duplicate = client.post(
        "/api/imports",
        headers=headers,
        files={
            "file": (
                workbook.name,
                workbook.read_bytes(),
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            )
        },
    )
    assert duplicate.status_code == 202
    duplicate_id = duplicate.json()["job_id"]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        duplicate_job = client.get(f"/api/jobs/{duplicate_id}", headers=headers).json()
        if duplicate_job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("duplicate import job did not finish")
    assert duplicate_job["status"] == "succeeded", duplicate_job["error"]


def test_import_rejects_invalid_office_container(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    response = client.post(
        "/api/imports",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "invalid.xlsx",
                b"not an Office ZIP container",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "bad_request"
    assert response.json()["message"] == "Workbook is not a valid Office file"


def test_import_enforces_configured_size_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("PE3_MAX_IMPORT_BYTES", "10")
    client = _client(tmp_path)
    token = _auth(client)
    response = client.post(
        "/api/imports",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "large.xlsx",
                b"01234567890",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_visibility_whitelist_blocks_materials_and_charts(tmp_path):
    client = _client(tmp_path)
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    db_path = os.environ["PE3_DB_PATH"]
    con = duckdb.connect(db_path)
    try:
        row = con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()
        mid = int(row[0])
        con.execute(
            "INSERT INTO settings(key, value_json) VALUES ('visible_material_codes', '[\"NOPE\"]') ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
        )
    finally:
        con.close()

    r = client.get("/api/materials?q=MAT-001", headers=h)
    assert r.status_code == 200
    assert r.json() == []

    # The seeded material_id is no longer visible, so charts should 404.
    r = client.get(f"/api/charts?material_id={mid}", headers=h)
    assert r.status_code in (404, 422)

    r = client.get("/api/lots", headers=h)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_master_data_contact_crud_and_not_found_contract(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    payload = {
        "name": "QC Contact",
        "email": "qc@example.test",
        "group_name": "QC",
        "active": True,
    }

    created = client.post("/api/master-data/contacts", headers=headers, json=payload)
    assert created.status_code == 200
    contact_id = created.json()["contact_id"]

    updated = client.put(
        f"/api/master-data/contacts/{contact_id}",
        headers=headers,
        json={**payload, "name": "Updated QC"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated QC"
    assert any(
        row["contact_id"] == contact_id
        for row in client.get("/api/master-data/contacts", headers=headers).json()
    )

    assert client.delete(f"/api/master-data/contacts/{contact_id}", headers=headers).status_code == 204
    missing = client.put(
        f"/api/master-data/contacts/{contact_id}",
        headers=headers,
        json=payload,
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_master_data_can_update_unit_of_referenced_property(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    properties = client.get("/api/master-data/properties", headers=headers)
    assert properties.status_code == 200
    prop = next(row for row in properties.json() if row["name"] == "Allungamento")
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    try:
        material_id = int(con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()[0])
        con.execute(
            """
            INSERT INTO tolerances(
                tolerance_id, material_id, property_id, warn_low, warn_high,
                alarm_low, alarm_high, updated_at
            ) VALUES (?, ?, ?, 1, 2, 0, 3, CURRENT_TIMESTAMP)
            """,
            [int(new_id()), material_id, int(prop["property_id"])],
        )
        con.execute(
            "INSERT INTO rating_property_weights(property_id, weight) VALUES (?, 2.5)",
            [int(prop["property_id"])],
        )
        con.execute(
            "INSERT INTO rating_property_rules(property_id, rule_json) VALUES (?, '{\"type\":\"test\"}')",
            [int(prop["property_id"])],
        )
    finally:
        con.close()

    updated = client.put(
        f"/api/master-data/properties/{prop['property_id']}",
        headers=headers,
        json={**prop, "unit": "%"},
    )

    assert updated.status_code == 200
    assert updated.json()["unit"] == "%"
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    try:
        property_id = int(prop["property_id"])
        assert con.execute("SELECT COUNT(*) FROM measurements WHERE property_id = ?", [property_id]).fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM tolerances WHERE property_id = ?", [property_id]).fetchone()[0] == 1
        assert con.execute("SELECT weight FROM rating_property_weights WHERE property_id = ?", [property_id]).fetchone()[0] == 2.5
        assert con.execute("SELECT rule_json FROM rating_property_rules WHERE property_id = ?", [property_id]).fetchone()[0] == '{"type":"test"}'
    finally:
        con.close()


def test_lots_server_pagination_and_material_test_filters(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    db_path = os.environ["PE3_DB_PATH"]
    con = duckdb.connect(db_path)
    try:
        visible_id = con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()[0]
        hidden_id = int(new_id())
        hidden_test_id = int(new_id())
        visible_test_id = int(new_id())
        con.execute("INSERT INTO materials(material_id, code, active) VALUES (?, 'HIDDEN', TRUE)", [hidden_id])
        con.execute(
            "INSERT INTO tests(test_id, material_id, request_date, created_at) VALUES (?, ?, DATE '2027-01-01', CURRENT_TIMESTAMP)",
            [hidden_test_id, hidden_id],
        )
        con.execute(
            "INSERT INTO tests(test_id, material_id, request_date, created_at) VALUES (?, ?, DATE '2026-02-01', CURRENT_TIMESTAMP)",
            [visible_test_id, visible_id],
        )
    finally:
        con.close()
    page1 = client.get("/api/lots?limit=1&offset=0", headers=headers)
    page2 = client.get("/api/lots?limit=1&offset=1", headers=headers)
    assert page1.status_code == page2.status_code == 200
    assert page1.json()["items"][0]["test_id"] == str(visible_test_id)
    assert page2.json()["items"][0]["material_id"] == str(visible_id)
    assert page1.json()["total"] >= 2
    assert page1.json()["has_next"] is True
    assert client.get(f"/api/lots?test_id={visible_test_id}", headers=headers).json()["items"][0]["test_id"] == str(visible_test_id)
    assert client.get(f"/api/lots?material_id={hidden_id}", headers=headers).json()["items"] == []
    assert client.get("/api/lots?limit=2001", headers=headers).status_code == 422


def test_lots_server_search_date_status_and_sort_filters(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    db_path = os.environ["PE3_DB_PATH"]
    con = duckdb.connect(db_path)
    try:
        material_id = con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()[0]
        awaiting_production_id = int(new_id())
        awaiting_analysis_id = int(new_id())
        completed_id = int(new_id())
        con.execute(
            "INSERT INTO tests(test_id, material_id, request_date, created_at) VALUES (?, ?, DATE '2028-01-01', CURRENT_TIMESTAMP)",
            [awaiting_production_id, material_id],
        )
        con.execute(
            "INSERT INTO tests(test_id, material_id, request_date, prod_date, created_at) VALUES (?, ?, DATE '2029-01-01', DATE '2029-01-02', CURRENT_TIMESTAMP)",
            [awaiting_analysis_id, material_id],
        )
        con.execute(
            "INSERT INTO tests(test_id, material_id, request_date, prod_date, analysis_date, created_at) VALUES (?, ?, DATE '2030-01-01', DATE '2030-01-02', DATE '2030-01-03', CURRENT_TIMESTAMP)",
            [completed_id, material_id],
        )
        con.execute(
            "INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code) VALUES (?, 'ISO', 'ISO-FILTER', 'Filter test', 'LOT-1')",
            [completed_id],
        )
        con.execute(
            "INSERT INTO measurements(measurement_id, test_id, property_id, value_num, value_text) VALUES (?, ?, 13, 72.5, NULL)",
            [int(new_id()), completed_id],
        )
    finally:
        con.close()

    awaiting = client.get(
        f"/api/lots?status=awaiting_production&q={awaiting_production_id}", headers=headers
    )
    assert awaiting.status_code == 200
    assert [row["test_id"] for row in awaiting.json()["items"]] == [str(awaiting_production_id)]

    completed = client.get(f"/api/lots?status=completed&q={completed_id}", headers=headers)
    assert completed.status_code == 200
    assert [row["test_id"] for row in completed.json()["items"]] == [str(completed_id)]

    component_and_qc = client.get(
        "/api/lots?iso=iso-filter&qc_field=durezza&qc_min=70&qc_max=75", headers=headers
    )
    assert component_and_qc.status_code == 200
    assert component_and_qc.json()["total"] == 1
    assert component_and_qc.json()["items"][0]["test_id"] == str(completed_id)

    ordered = client.get(
        "/api/lots?date_field=request_date&date_from=2028-01-01&date_to=2030-01-01&sort_by=request_date&sort_dir=asc&limit=3",
        headers=headers,
    )
    assert ordered.status_code == 200
    assert [row["test_id"] for row in ordered.json()["items"]] == [
        str(awaiting_production_id), str(awaiting_analysis_id), str(completed_id)
    ]
    assert client.get("/api/lots?sort_by=not_a_column", headers=headers).status_code == 422


def test_settings_role_and_user_crud(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    role_payload = {
        "name": "LabOperator",
        "can_edit_master": False,
        "can_edit_tests": True,
        "can_manage_users": False,
        "can_send_outlook": False,
    }

    role_response = client.post("/api/settings/roles", headers=headers, json=role_payload)
    assert role_response.status_code == 200
    role_id = role_response.json()["role_id"]

    updated_role = client.put(
        f"/api/settings/roles/{role_id}",
        headers=headers,
        json={**role_payload, "can_send_outlook": True},
    )
    assert updated_role.status_code == 200
    assert updated_role.json()["can_send_outlook"] is True

    user_response = client.post(
        "/api/settings/users",
        headers=headers,
        json={"username": "operator", "password": "initial", "role_id": role_id, "active": True},
    )
    assert user_response.status_code == 200
    user_id = user_response.json()["user_id"]

    referenced_role = client.put(
        f"/api/settings/roles/{role_id}",
        headers=headers,
        json={**role_payload, "can_edit_master": True},
    )
    assert referenced_role.status_code == 409
    assert referenced_role.json()["code"] == "conflict"

    assert client.post(
        f"/api/settings/users/{user_id}/reset-password",
        headers=headers,
        json={"new_password": "changed"},
    ).status_code == 204
    assert client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "changed"},
    ).status_code == 200

    assert client.delete(f"/api/settings/users/{user_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/settings/roles/{role_id}", headers=headers).status_code == 204


def test_settings_rating_rule_validates_band_semantics(tmp_path):
    client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {_auth(client)}"}
    rows = client.get("/api/settings/ratings", headers=headers)
    assert rows.status_code == 200
    property_id = rows.json()[0]["property_id"]

    invalid = client.put(
        f"/api/settings/ratings/{property_id}/rule",
        headers=headers,
        json={"rule_json": '{"type":"not-a-rating-rule"}'},
    )
    assert invalid.status_code == 400
    assert "Unsupported rule type" in invalid.json()["detail"]

    rule_json = (
        '{"type":"pct_from_avg_bands_v1","bands":['
        '{"max_pct":1,"points":20},{"max_pct":2,"points":10},'
        '{"max_pct":null,"points":0}],"max_points":20}'
    )
    saved = client.put(
        f"/api/settings/ratings/{property_id}/rule",
        headers=headers,
        json={"rule_json": rule_json},
    )
    assert saved.status_code == 204
    refreshed = client.get("/api/settings/ratings", headers=headers).json()
    assert next(row for row in refreshed if row["property_id"] == property_id)["rule_json"] == rule_json


def test_master_data_and_settings_are_backend_authorized(tmp_path):
    client = _client(tmp_path)
    login = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    master = client.get("/api/master-data/contacts", headers=headers)
    settings = client.get("/api/settings/thresholds", headers=headers)

    assert master.status_code == 403
    assert master.json()["code"] == "forbidden"
    assert settings.status_code == 403
    assert settings.json()["code"] == "forbidden"
