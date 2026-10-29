from __future__ import annotations

import os
import shutil

import duckdb

from backend.app.schemas.master_data import ToleranceUpsertRequest
from backend.app.services.master_data import MasterDataService
from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db import migrations
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.tolerances_repo import ensure_material_tolerance, list_tolerances
from pe3_qc_app.services.qc_failures_service import fetch_alarm_tolerance_failures
from test_web_api import _client


def test_migration_upgrades_a_copy_without_changing_existing_bounds(tmp_path):
    original = tmp_path / "prior.duckdb"
    con = duckdb.connect(str(original))
    con.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    prior_migrations = (
        migrations._m001_init, migrations._m002_indexes, migrations._m003_test_component_lots,
        migrations._m004_lastrine_notify_template, migrations._m005_charts_tolerance_pct_setting,
        migrations._m006_components_master_data, migrations._m007_i18n_locales,
        migrations._m008_sample_request_queue, migrations._m009_rating_system,
        migrations._m010_prod_date_indexes, migrations._m011_import_jobs,
    )
    for migrate in prior_migrations:
        migrate(con)
    con.execute("INSERT INTO schema_version VALUES (11)")
    con.execute("INSERT INTO properties(property_id, name, data_type, active) VALUES (1, 'Test', 'num', TRUE)")
    con.execute("INSERT INTO tolerances(tolerance_id, property_id, alarm_low, alarm_high, updated_at) VALUES (1, 1, 80, 120, CURRENT_TIMESTAMP)")
    con.close()
    upgraded = tmp_path / "upgraded.duckdb"
    shutil.copy2(original, upgraded)
    con = duckdb.connect(str(upgraded))
    apply_migrations(con)
    apply_migrations(con)
    row = list_tolerances(con)[0]
    assert (row.alarm_low, row.alarm_high) == (80, 120)
    assert (row.alarm_low_input, row.alarm_high_input) == (80, 120)
    assert row.alarm_low_mode == "absolute"
    assert row.is_custom is False
    con.close()
    con = duckdb.connect(str(original))
    assert con.execute("SELECT version FROM schema_version").fetchone()[0] == 11
    con.close()


def test_v12_reference_limit_is_recognized_as_custom_on_upgrade(tmp_path):
    source = tmp_path / "v12.duckdb"
    con = duckdb.connect(str(source))
    apply_migrations(con)
    con.execute("INSERT INTO properties(property_id, name, data_type, active) VALUES (1, 'Test', 'num', TRUE)")
    con.execute("""
        INSERT INTO tolerances(tolerance_id, property_id, reference_value, alarm_low, alarm_high,
                               alarm_low_input, alarm_high_input, alarm_low_mode, alarm_high_mode, updated_at, is_custom)
        VALUES (1, 1, 100, 90, 110, 10, 10, 'percent', 'percent', CURRENT_TIMESTAMP, FALSE)
    """)
    con.execute("UPDATE schema_version SET version=12")
    con.close()
    upgraded = tmp_path / "v13.duckdb"
    shutil.copy2(source, upgraded)
    con = duckdb.connect(str(upgraded))
    apply_migrations(con)
    assert list_tolerances(con)[0].is_custom is True
    con.close()


def test_reference_percent_and_numeric_limits_round_trip(tmp_path):
    client = _client(tmp_path)
    token = client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    material_id = con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()[0]
    test_id = int(new_id())
    con.execute("INSERT INTO tests(test_id, material_id, prod_date, created_at) VALUES (?, ?, DATE '2026-01-02', CURRENT_TIMESTAMP)", [test_id, material_id])
    con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num) VALUES (?, ?, 10, 100)", [int(new_id()), test_id])
    second_test = int(new_id())
    con.execute("INSERT INTO tests(test_id, material_id, prod_date, created_at) VALUES (?, ?, DATE '2026-01-03', CURRENT_TIMESTAMP)", [second_test, material_id])
    con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num) VALUES (?, ?, 10, 200)", [int(new_id()), second_test])
    con.close()
    payload = {
        "material_id": material_id, "property_id": 10, "reference_value": 100,
        "warn_low_input": 5, "warn_low_mode": "percent",
        "warn_high_input": 108, "warn_high_mode": "absolute",
        "alarm_low_input": 10, "alarm_low_mode": "percent",
        "alarm_high_input": 115, "alarm_high_mode": "absolute",
    }
    saved = client.post("/api/master-data/tolerances", json=payload, headers=headers)
    assert saved.status_code == 200, saved.text
    row = saved.json()
    assert (row["warn_low"], row["warn_high"], row["alarm_low"], row["alarm_high"]) == (95, 108, 90, 115)
    assert row["warn_low_input"] == 5
    assert client.get("/api/master-data/tolerances", headers=headers).json()[0]["reference_value"] == 100
    duplicate = client.post("/api/master-data/tolerances", json=payload, headers=headers)
    assert duplicate.status_code == 422
    bad = dict(payload, alarm_low_input=1)
    assert client.put(f"/api/master-data/tolerances/{row['tolerance_id']}", json=bad, headers=headers).status_code == 422
    chart = client.get(f"/api/charts/panels?material_id={material_id}&smooth=false", headers=headers)
    smooth_chart = client.get(f"/api/charts/panels?material_id={material_id}&smooth=true", headers=headers)
    assert chart.status_code == smooth_chart.status_code == 200
    traces = chart.json()["panels"][0]["traces"]
    smooth_traces = smooth_chart.json()["panels"][0]["traces"]
    alarm_low = next(trace for trace in traces if trace["name"] == "Alarm low")
    assert alarm_low["y"][0] == 90
    assert next(trace for trace in traces if trace["name"] == "Reference")["y"][0] == 100
    assert next(trace for trace in traces if trace["name"] == "Average")["y"][0] == 150
    assert next(trace for trace in smooth_traces if trace["name"] == "Average")["y"][0] == 150
    assert any("T" in x for x in smooth_traces[0]["x"])
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    try:
        _, failures = fetch_alarm_tolerance_failures(con, test_id=second_test)
        assert any(failure.property_name == "Lacerazione B" for failure in failures)
    finally:
        con.close()


def test_legacy_absolute_payload_remains_supported(tmp_path):
    con = duckdb.connect(str(tmp_path / "legacy.duckdb"))
    apply_migrations(con)
    con.execute("INSERT INTO properties(property_id, name, data_type, active) VALUES (1, 'Test', 'num', TRUE)")
    service = MasterDataService()
    row = service.save_tolerance(con, tolerance_id=None, payload=ToleranceUpsertRequest(property_id=1, alarm_low=2, alarm_high=4))
    assert (row.alarm_low, row.alarm_high, row.alarm_low_input, row.alarm_high_input) == (2, 4, 2, 4)
    assert row.is_custom is True
    con.close()


def test_new_tolerance_replaces_generated_fallback(tmp_path):
    client = _client(tmp_path)
    token = client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    material_id = int(con.execute("SELECT material_id FROM materials WHERE code='MAT-001'").fetchone()[0])
    ensure_material_tolerance(con, material_id=material_id, property_id=10,
                              warn_low=None, warn_high=None, alarm_low=80, alarm_high=120)
    old = next(row for row in list_tolerances(con) if row.material_id == material_id and row.property_id == 10)
    assert old.is_custom is False
    con.close()
    saved = client.post("/api/master-data/tolerances", json={
        "material_id": material_id, "property_id": 10, "reference_value": 100,
        "alarm_low_input": 90, "alarm_high_input": 110,
    }, headers=headers)
    assert saved.status_code == 200, saved.text
    assert int(saved.json()["tolerance_id"]) == old.tolerance_id
    assert saved.json()["is_custom"] is True
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    assert len([row for row in list_tolerances(con) if row.material_id == material_id and row.property_id == 10]) == 1
    con.close()


def test_explicit_hardness_tolerance_overrides_description_rule(tmp_path):
    client = _client(tmp_path)
    token = client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    material_id, test_id = int(new_id()), int(new_id())
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    con.execute("INSERT INTO materials(material_id, code, description, active) VALUES (?, 'HARD-80', '80 ShA', TRUE)", [material_id])
    con.execute("INSERT INTO sinottico_items(item_id, material_id, active) VALUES (?, ?, TRUE)", [int(new_id()), material_id])
    con.execute("INSERT INTO tests(test_id, material_id, prod_date, created_at) VALUES (?, ?, DATE '2026-01-02', CURRENT_TIMESTAMP)", [test_id, material_id])
    con.execute("INSERT INTO measurements(measurement_id, test_id, property_id, value_num) VALUES (?, ?, 13, 80)", [int(new_id()), test_id])
    con.close()
    saved = client.post("/api/master-data/tolerances", json={
        "material_id": material_id, "property_id": 13, "reference_value": 80,
        "alarm_low_input": 70, "alarm_high_input": 90,
    }, headers=headers)
    assert saved.status_code == 200, saved.text
    chart = client.get(f"/api/charts/panels?material_id={material_id}&smooth=false", headers=headers)
    assert chart.status_code == 200, chart.text
    traces = chart.json()["panels"][3]["traces"]
    assert next(trace for trace in traces if trace["name"] == "Alarm low")["y"] == [70]
    default = client.post("/api/master-data/tolerances", json={
        "property_id": 13, "reference_value": 80, "alarm_low_input": 60, "alarm_high_input": 100,
    }, headers=headers)
    assert default.status_code == 200, default.text
    assert client.delete(f"/api/master-data/tolerances/{saved.json()['tolerance_id']}", headers=headers).status_code == 204
    con = duckdb.connect(os.environ["PE3_DB_PATH"])
    ensure_material_tolerance(con, material_id=material_id, property_id=13,
                              warn_low=None, warn_high=None, alarm_low=78, alarm_high=82)
    con.close()
    fallback = client.get(f"/api/charts/panels?material_id={material_id}&smooth=false", headers=headers)
    assert next(trace for trace in fallback.json()["panels"][3]["traces"] if trace["name"] == "Alarm low")["y"] == [60]
