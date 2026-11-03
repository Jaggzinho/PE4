from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import shutil
from threading import Event
import time

import jwt
import openpyxl
import pytest
from fastapi.testclient import TestClient

from backend.app.config import load_config
from backend.app.main import create_app
from pe3_qc_app.db.db_manager import DbManager
from tests.test_web_api import _seed_db


IDS = ("tcm_ro", "wam_ro", "tcm_it", "wam_wuxi")
SECRET = "environment-tests-secret-at-least-32-characters"


@pytest.fixture
def application(tmp_path, monkeypatch):
    # Rehearse startup against an offline copy, never a user's database.
    prior = tmp_path / "prior.duckdb"
    _seed_db(str(prior))
    active = tmp_path / "active.duckdb"
    shutil.copy2(prior, active)
    monkeypatch.setenv("PE3_DB_PATH", str(active))
    monkeypatch.setenv("PE3_WEB_CONFIG_PATH", str(tmp_path / "web-config.json"))
    monkeypatch.setenv("PE3_JWT_SECRET", SECRET)
    monkeypatch.setenv("PE3_SETUP_TOKEN", "setup-token")
    monkeypatch.setenv("PE3_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PE3_AUTH_DB_PATH", raising=False)
    app = create_app()
    with TestClient(app) as client:
        yield client


def headers(client, environment="tcm_ro", username="admin", password="pw"):
    response = client.post("/api/auth/login", json={
        "username": username, "password": password, "environment_id": environment,
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def workbook():
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "materiali"
    sheet.append(["codice mat", "desc materiale", "cod lastrina", "desc last"])
    sheet.append(["IMPORTED-001", "Same template", "PLATE", "Plate description"])
    stream = BytesIO()
    wb.save(stream)
    wb.close()
    return stream.getvalue()


def test_registry_shared_login_and_empty_qc_databases(application, tmp_path):
    client = application
    registry = client.get("/api/environments").json()
    assert [item["environment_id"] for item in registry] == list(IDS)
    assert [item["label"] for item in registry] == ["TCM Romania", "WAM Romania", "TCM Italia", "WAM WuXi"]
    assert [item["flag_key"] for item in registry] == ["ro", "ro", "it", "cn"]
    assert all(item["available"] for item in registry)
    assert not any("path" in key for item in registry for key in item)
    state = client.app.state.pe3_state
    with DbManager(tmp_path / "prior.duckdb").connect() as con:
        original_users = con.execute("SELECT user_id, pw_salt, pw_hash FROM users ORDER BY user_id").fetchall()
    with state.auth_db.connect() as con:
        assert con.execute("SELECT user_id, pw_salt, pw_hash FROM users ORDER BY user_id").fetchall() == original_users
    for sid in IDS:
        h = headers(client, sid)
        me = client.get("/api/auth/me", headers=h).json()
        assert me["environment"]["environment_id"] == sid
        assert me["username"] == "admin"
        with state.environments[sid].db.connect() as con:
            assert con.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == (1 if sid == "tcm_ro" else 0)
            assert con.execute("SELECT COUNT(*) FROM tests").fetchone()[0] == (1 if sid == "tcm_ro" else 0)
    assert client.get("/api/setup/status").json() == {"needs_setup": False}
    assert client.post("/api/setup/first-admin", headers={"X-PE3-SETUP-TOKEN": "setup-token"},
                       json={"username": "another", "password": "pw", "password2": "pw"}).status_code == 409


def test_overlapping_ids_writes_queues_settings_and_permissions_are_isolated(application):
    client = application
    state = client.app.state.pe3_state
    for sid in IDS:
        with state.environments[sid].db.write() as con:
            con.execute("INSERT INTO materials(material_id, code, active) VALUES (123, ?, TRUE)", [sid])
            con.execute("INSERT INTO sinottico_items(item_id, machine_code, material_id, active) VALUES (123, ?, 123, TRUE)", [sid])
            con.execute("INSERT INTO settings VALUES ('visible_material_codes', '[]') ON CONFLICT(key) DO UPDATE SET value_json='[]'")
    sessions = {sid: headers(client, sid) for sid in IDS}
    for sid, h in sessions.items():
        material = next(row for row in client.get("/api/materials", headers=h).json() if row["material_id"] == "123")
        assert material["code"] == sid
        response = client.post("/api/lots", headers=h, json={"material_id": "123"})
        assert response.status_code == 200, response.text
        assert response.json()["material_id"] == "123"
        another = sessions[IDS[(IDS.index(sid) + 1) % len(IDS)]]
        assert client.get(f"/api/lots/{response.json()['test_id']}", headers=another).status_code == 404
        assert client.post("/api/sinottico/queue/items/123", headers=h).status_code == 204
        assert len(client.get("/api/sinottico/queue", headers=h).json()) == 1
        readonly = headers(client, sid, "viewer")
        assert client.post("/api/lots", headers=readonly, json={"material_id": "123"}).status_code == 403
        assert client.put("/api/settings/thresholds", headers=readonly, json={"green_days": 2, "yellow_days": 3}).status_code == 403
    target = sessions["tcm_it"]
    assert client.put("/api/settings/thresholds", headers=target, json={"green_days": 2, "yellow_days": 3}).status_code == 200
    for sid, h in sessions.items():
        assert client.get("/api/settings/thresholds", headers=h).json()["green_days"] == (2 if sid == "tcm_it" else 90)
    assert client.delete("/api/sinottico/queue", headers=target).status_code == 204
    assert len(client.get("/api/sinottico/queue", headers=sessions["wam_ro"]).json()) == 1
    with state.environments["tcm_it"].db.connect() as con:
        projection = con.execute("SELECT active, pw_hash FROM users WHERE username='admin'").fetchone()
        assert projection is not None and projection[0] is False


def test_shared_account_changes_and_historical_deletion_constraints(application):
    client = application
    admin = headers(client)
    viewer_sessions = [headers(client, sid, "viewer") for sid in IDS]
    users = client.get("/api/settings/users", headers=admin).json()
    viewer = next(user for user in users if user["username"] == "viewer")
    admin_user = next(user for user in users if user["username"] == "admin")
    # A user referenced by TCM history cannot be deleted from another environment.
    assert client.delete(f"/api/settings/users/{admin_user['user_id']}", headers=headers(client, "wam_wuxi")).status_code == 409
    assert client.put(f"/api/settings/users/{viewer['user_id']}", headers=admin,
                      json={"role_id": viewer["role_id"], "active": False}).status_code == 200
    assert all(client.get("/api/auth/me", headers=h).status_code == 401 for h in viewer_sessions)
    assert client.post("/api/auth/login", json={"username": "viewer", "password": "pw", "environment_id": "tcm_it"}).status_code == 401
    assert client.put(f"/api/settings/users/{viewer['user_id']}", headers=admin,
                      json={"role_id": "1", "active": True}).status_code == 200
    # Existing tokens use current role permissions, rather than stale JWT claims.
    assert client.get("/api/settings/users", headers=viewer_sessions[-1]).status_code == 200
    assert client.post(f"/api/settings/users/{viewer['user_id']}/reset-password", headers=admin,
                       json={"new_password": "new-password"}).status_code == 204
    for sid in IDS:
        headers(client, sid, "viewer", "new-password")
        assert client.post("/api/auth/login", json={"username": "viewer", "password": "pw", "environment_id": sid}).status_code == 401


def test_same_import_template_and_duplicate_handling_in_every_environment(application):
    client = application
    data = workbook()
    state = client.app.state.pe3_state
    for index, sid in enumerate(IDS):
        h = headers(client, sid)
        for _ in range(2):
            response = client.post("/api/import/xlsm", headers=h,
                                   files={"file": ("template.xlsx", data, "application/octet-stream")})
            assert response.status_code == 200, response.text
            assert response.json()["result"]["materials"] == 1
        for other in IDS:
            with state.environments[other].db.connect() as con:
                count = con.execute("SELECT COUNT(*) FROM materials WHERE code='IMPORTED-001'").fetchone()[0]
            assert count == (1 if IDS.index(other) <= index else 0)


def test_background_import_is_pinned_and_jobs_do_not_cross_environments(application, monkeypatch):
    client = application
    started, release = Event(), Event()
    from pe3_qc_app.importer.import_models import ImportResult

    def delayed(con, _path, _progress):
        con.execute("INSERT INTO materials(material_id, code, active) VALUES (321, 'PINNED', TRUE)")
        started.set()
        assert release.wait(10)
        return ImportResult(materials=1, properties=0, tests=0, measurements=0, sinottico_items=0)

    monkeypatch.setattr("backend.app.jobs.manager.import_workbook", delayed)
    source, other = headers(client, "wam_ro"), headers(client, "tcm_it")
    try:
        response = client.post("/api/imports", headers=source, files={"file": ("template.xlsx", workbook(), "application/octet-stream")})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert started.wait(10)
        assert client.get(f"/api/jobs/{job_id}", headers=other).status_code == 404
        assert client.get("/api/jobs", headers=other).json() == []
        # Another environment remains usable while the first import holds a write transaction.
        assert client.post("/api/master-data/materials", headers=other, json={"code": "OTHER"}).status_code == 200
    finally:
        release.set()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}", headers=source).json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.02)
    assert job["status"] == "succeeded", job
    state = client.app.state.pe3_state
    for sid in IDS:
        with state.environments[sid].db.connect() as con:
            assert con.execute("SELECT COUNT(*) FROM materials WHERE code='PINNED'").fetchone()[0] == (1 if sid == "wam_ro" else 0)


def test_invalid_tokens_environment_overrides_and_unavailable_environment(application):
    client = application
    for sid in ("unknown", "../qc.duckdb", "TCM Romania", ""):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "pw", "environment_id": sid})
        assert response.status_code == 400
        assert response.json()["code"] == "bad_request"
    h = headers(client, "tcm_it")
    assert client.get("/api/materials?environment_id=tcm_ro", headers={**h, "X-Environment-ID": "tcm_ro"}).json() == []
    payload = jwt.decode(h["Authorization"].split()[1], SECRET, algorithms=["HS256"])
    for sid in (None, "invalid"):
        invalid = dict(payload)
        invalid.pop("environment_id")
        if sid:
            invalid["environment_id"] = sid
        token = jwt.encode(invalid, SECRET, algorithm="HS256")
        assert client.get("/api/materials", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    state = client.app.state.pe3_state
    state.environments["tcm_it"] = replace(state.environments["tcm_it"], db=None)
    assert client.get("/api/materials", headers=h).status_code == 503
    assert client.post("/api/auth/login", json={"username": "admin", "password": "pw", "environment_id": "tcm_it"}).status_code == 503
    assert client.get("/api/environments").json()[2]["available"] is False


def test_database_registry_rejects_aliases_and_settings_are_environment_specific(application, tmp_path, monkeypatch):
    client = application
    state = client.app.state.pe3_state
    h = headers(client, "wam_ro")
    url = "/api/settings/database-source"
    for candidate in (state.auth_db.db_path, state.db.db_path, state.environments["tcm_it"].db.db_path):
        assert client.put(url, headers=h, json={"path": str(candidate)}).status_code == 400
    replacement = tmp_path / "next.duckdb"
    shutil.copy2(tmp_path / "prior.duckdb", replacement)
    assert client.put(url, headers=h, json={"path": str(replacement)}).status_code == 200
    saved = json.loads((tmp_path / "web-config.json").read_text())
    assert saved["environments"] == {"wam_ro": str(replacement)}
    assert "db_path" not in saved
    assert client.get(url, headers=headers(client)).json()["configured_next_path"] is None
    # Pending paths also cannot be shared by a different environment.
    assert client.put(url, headers=headers(client, "tcm_it"), json={"path": str(replacement)}).status_code == 400
    config = load_config()
    assert next(env for env in config.environments if env.environment_id == "wam_ro").db_path == replacement
    saved["environments"]["tcm_it"] = str(replacement)
    (tmp_path / "web-config.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="distinct"):
        load_config()


def test_restart_preserves_shared_password_changes_without_reimporting(application):
    client = application
    h = headers(client)
    viewer = next(user for user in client.get("/api/settings/users", headers=h).json() if user["username"] == "viewer")
    assert client.post(f"/api/settings/users/{viewer['user_id']}/reset-password", headers=h,
                       json={"new_password": "changed"}).status_code == 204
    with TestClient(create_app()) as restarted:
        assert restarted.get("/api/setup/status").json() == {"needs_setup": False}
        for sid in IDS:
            headers(restarted, sid, "viewer", "changed")
        assert restarted.post("/api/auth/login", json={"username": "viewer", "password": "pw"}).status_code == 401
        with restarted.app.state.pe3_state.auth_db.connect() as con:
            assert con.execute("SELECT version FROM identity_schema_version").fetchall() == [(1,)]


def test_missing_additional_environment_fails_closed_without_blocking_other_logins(application, tmp_path):
    missing = tmp_path / "missing.duckdb"
    (tmp_path / "web-config.json").write_text(json.dumps({"environments": {"wam_ro": str(missing)}}))
    with TestClient(create_app()) as restarted:
        assert not missing.exists()
        registry = restarted.get("/api/environments").json()
        assert registry[1]["available"] is False
        for sid in ("tcm_ro", "tcm_it", "wam_wuxi"):
            headers(restarted, sid)
        assert restarted.post("/api/auth/login", json={"username": "admin", "password": "pw", "environment_id": "wam_ro"}).status_code == 503
