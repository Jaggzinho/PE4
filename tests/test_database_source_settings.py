from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.config import load_config
from backend.app.main import create_app
from tests.test_web_api import _auth, _seed_db


def test_database_source_permissions_validation_and_next_startup(tmp_path, monkeypatch):
    active = tmp_path / "active.duckdb"
    next_db = tmp_path / "next.duckdb"
    invalid = tmp_path / "invalid.duckdb"
    config_file = tmp_path / "web-config.json"
    _seed_db(str(active))
    _seed_db(str(next_db))
    invalid.write_text("not a database", encoding="utf-8")
    config_file.write_text(json.dumps({"other_setting": "preserve"}), encoding="utf-8")
    monkeypatch.setenv("PE3_DB_PATH", str(active))
    monkeypatch.setenv("PE3_WEB_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("PE3_JWT_SECRET", "test-secret-at-least-32-characters-long")
    monkeypatch.delenv("PE3_DB_SOURCE", raising=False)
    client = TestClient(create_app())
    viewer = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"}).json()
    viewer_h = {"Authorization": f"Bearer {viewer['access_token']}"}
    admin_h = {"Authorization": f"Bearer {_auth(client)}"}
    url = "/api/settings/database-source"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=viewer_h).status_code == 403
    assert client.put(url, headers=viewer_h, json={"path": str(next_db)}).status_code == 403

    before = client.get(url, headers=admin_h).json()
    assert before["active_path"] == str(active)
    assert before["active_source"] == "environment"
    assert before["override_active"] is True
    for candidate in (str(tmp_path / "missing.duckdb"), str(invalid), "https://example.test/db.duckdb", "relative.duckdb"):
        response = client.put(url, headers=admin_h, json={"path": candidate})
        assert response.status_code == 400
    assert json.loads(config_file.read_text(encoding="utf-8")) == {"other_setting": "preserve"}

    saved = client.put(url, headers=admin_h, json={"path": str(next_db)})
    assert saved.status_code == 200
    assert saved.json()["configured_next_path"] == str(next_db)
    assert saved.json()["restart_required"] is True
    assert saved.json()["active_path"] == str(active)
    assert client.app.state.pe3_state.db.db_path == active
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "other_setting": "preserve", "db_path": str(next_db),
    }
    assert load_config().db_path == active  # explicit environment override still wins

    monkeypatch.delenv("PE3_DB_PATH")
    assert load_config().db_path == next_db
    assert load_config().db_source == "local_config"
    restarted = TestClient(create_app())
    assert restarted.app.state.pe3_state.db.db_path == next_db
    assert client.app.state.pe3_state.db.db_path == active


def test_configured_missing_path_fails_closed(tmp_path, monkeypatch):
    config_file = tmp_path / "web-config.json"
    config_file.write_text(json.dumps({"db_path": str(tmp_path / "missing.duckdb")}), encoding="utf-8")
    monkeypatch.setenv("PE3_WEB_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("PE3_DB_PATH", raising=False)
    monkeypatch.setenv("PE3_JWT_SECRET", "test-secret-at-least-32-characters-long")
    try:
        create_app()
    except RuntimeError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("A missing configured database must never create an empty database")
    assert not (tmp_path / "missing.duckdb").exists()
