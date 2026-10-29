from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path
from threading import Lock
import time

from fastapi.testclient import TestClient

from backend.app.main import create_app
from pe3_qc_app.db.db_manager import DbManager


def _configure(monkeypatch, db_path: Path, *, static_dir: Path | None = None) -> None:
    monkeypatch.setenv("PE3_DB_PATH", str(db_path))
    monkeypatch.setenv("PE3_JWT_SECRET", "test-secret-at-least-32-characters-long")
    monkeypatch.setenv("PE3_CORS_ORIGINS", "")
    monkeypatch.setenv("PE3_SETUP_TOKEN", "setup-token")
    monkeypatch.setenv("PE3_SUBSIDIARY_ID", "tcm_ro")
    if static_dir is None:
        monkeypatch.delenv("PE3_STATIC_DIR", raising=False)
    else:
        monkeypatch.setenv("PE3_STATIC_DIR", str(static_dir))


def test_write_transaction_rolls_back(tmp_path):
    manager = DbManager(tmp_path / "rollback.duckdb")
    with manager.connect() as con:
        con.execute("CREATE TABLE events(id INTEGER PRIMARY KEY)")

    try:
        with manager.write() as con:
            con.execute("INSERT INTO events VALUES (1)")
            raise ValueError("stop")
    except ValueError:
        pass

    with manager.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_write_transactions_are_serialized(tmp_path):
    manager = DbManager(tmp_path / "serialized.duckdb")
    with manager.connect() as con:
        con.execute("CREATE TABLE events(id INTEGER PRIMARY KEY)")

    guard = Lock()
    active = 0
    maximum_active = 0

    def write_event(event_id: int) -> None:
        nonlocal active, maximum_active
        with manager.write() as con:
            with guard:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.03)
            con.execute("INSERT INTO events VALUES (?)", [event_id])
            with guard:
                active -= 1

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write_event, range(4)))

    assert maximum_active == 1
    with manager.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4


def test_api_errors_have_stable_code_and_message(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path / "errors.duckdb")
    client = TestClient(create_app())

    response = client.post("/api/auth/login", json={"username": "missing", "password": "bad"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.json()["message"] == "Invalid username/password"


def test_spa_fallback_never_masks_unknown_api(tmp_path, monkeypatch):
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>PE3 SPA</html>", encoding="utf-8")
    _configure(monkeypatch, tmp_path / "spa.duckdb", static_dir=static_dir)
    client = TestClient(create_app())

    page = client.get("/lots/123")
    missing_api = client.get("/api/does-not-exist")

    assert page.status_code == 200
    assert "PE3 SPA" in page.text
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert missing_api.json()["code"] == "not_found"


def test_legacy_double_api_prefix_is_not_exposed(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path / "routes.duckdb")
    client = TestClient(create_app())

    assert client.get("/api/health").status_code == 200
    response = client.get("/api/api/health")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_application_has_no_duplicate_routes(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path / "unique-routes.duckdb")
    app = create_app()
    route_keys = [
        (tuple(sorted(route.methods or [])), route.path)
        for route in app.routes
        if hasattr(route, "methods")
    ]

    duplicates = [key for key, count in Counter(route_keys).items() if count > 1]

    assert duplicates == []


def test_api_routes_are_owned_by_backend_modules(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path / "route-owners.duckdb")
    app = create_app()

    owners = {
        route.path: route.endpoint.__module__
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/") and hasattr(route, "endpoint")
    }

    assert owners
    assert all(owner.startswith("backend.app.") for owner in owners.values())


def test_deprecated_import_contract_is_preserved_and_documented(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path / "deprecated-import.duckdb")
    app = create_app()
    client = TestClient(app)

    setup = client.post(
        "/api/setup/first-admin",
        headers={"X-PE3-SETUP-TOKEN": "setup-token"},
        json={"username": "admin", "password": "pw", "password2": "pw"},
    )
    assert setup.status_code == 204
    login = client.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert login.status_code == 200

    response = client.post(
        "/api/import",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    operation = app.openapi()["paths"]["/api/import"]["post"]

    assert response.status_code == 501
    assert response.json()["code"] == "not_implemented"
    assert response.json()["message"] == "Not implemented in v1"
    assert operation["deprecated"] is True
    assert "501" in operation["responses"]


def test_backend_has_no_legacy_web_dependency():
    backend_root = Path(__file__).resolve().parents[1] / "backend"
    offenders = [
        path.relative_to(backend_root).as_posix()
        for path in backend_root.rglob("*.py")
        if "pe3_qc_app_web" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
