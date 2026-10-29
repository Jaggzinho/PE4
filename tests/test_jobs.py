from __future__ import annotations

from pathlib import Path
import time

from backend.app.jobs.manager import JobManager
from backend.app.db.repositories import import_jobs as jobs_repo
from pe3_qc_app.db.db_manager import DbManager
from pe3_qc_app.db.migrations import apply_migrations


def _wait(manager: JobManager, job_id: str):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = manager.get(job_id, owner_id=7)
        if snapshot.status in {"succeeded", "failed"}:
            return snapshot
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_failed_import_job_rolls_back_and_removes_upload(tmp_path, monkeypatch):
    database = DbManager(tmp_path / "jobs.duckdb")
    with database.connect() as con:
        apply_migrations(con)
        con.execute("CREATE TABLE imported_values(value INTEGER)")

    def failing_import(con, _path: Path, progress):
        progress("started")
        con.execute("INSERT INTO imported_values VALUES (1)")
        raise ValueError("invalid workbook data")

    monkeypatch.setattr("backend.app.jobs.manager.import_workbook", failing_import)
    upload = tmp_path / "upload.xlsx"
    upload.write_bytes(b"temporary")
    manager = JobManager(database)
    try:
        created = manager.submit_import(owner_id=7, workbook_path=upload)
        finished = _wait(manager, created.job_id)
    finally:
        manager.shutdown()

    assert finished.status == "failed"
    assert finished.progress < 100
    assert "invalid workbook data" in (finished.error or "")
    assert not upload.exists()
    with database.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM imported_values").fetchone()[0] == 0
    restarted = JobManager(database)
    try:
        persisted = restarted.get(created.job_id, owner_id=7)
        assert persisted.status == "failed"
        assert "invalid workbook data" in (persisted.error or "")
        assert persisted.messages == ["started"]
    finally:
        restarted.shutdown()


def test_restart_marks_interrupted_jobs_and_bounds_history(tmp_path):
    database = DbManager(tmp_path / "jobs.duckdb")
    with database.connect() as con:
        apply_migrations(con)
        from backend.app.jobs.manager import JobSnapshot

        for i in range(205):
            snapshot = JobSnapshot(job_id=f"job-{i:03}", owner_id=7, kind="workbook_import")
            snapshot.status = "running" if i == 204 else "succeeded"
            jobs_repo.insert(con, snapshot)
    manager = JobManager(database)
    try:
        interrupted = manager.get("job-204", owner_id=7)
        assert interrupted.status == "failed"
        assert "outcome may be uncertain" in (interrupted.error or "")
        assert len(manager.list_recent(owner_id=7, limit=50)) == 50
        assert len(manager.list_recent(owner_id=7, limit=500)) == 50
        assert len(manager.list_recent(owner_id=8)) == 0
        assert len(manager.list_recent(owner_id=8, can_manage=True, limit=50)) == 50
        with database.connect() as con:
            assert con.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0] == 200
    finally:
        manager.shutdown()


def test_job_migration_upgrades_copy_and_is_idempotent(tmp_path):
    source = tmp_path / "prior.duckdb"
    copy = tmp_path / "copy.duckdb"
    with DbManager(source).connect() as con:
        apply_migrations(con)
        con.execute("DROP TABLE import_jobs")
        con.execute("UPDATE schema_version SET version=10")
    import shutil
    shutil.copy2(source, copy)
    with DbManager(copy).connect() as con:
        apply_migrations(con)
        apply_migrations(con)
        assert con.execute("SELECT version FROM schema_version").fetchone()[0] == 13
        assert con.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0] == 0
    with DbManager(source).connect() as con:
        assert con.execute("SELECT version FROM schema_version").fetchone()[0] == 10


def test_job_history_api_respects_owner_and_exposes_failure(tmp_path):
    from tests.test_web_api import _auth, _client
    from backend.app.jobs.manager import JobSnapshot

    client = _client(tmp_path)
    jobs = client.app.state.pe3_state.jobs
    admin = {"Authorization": f"Bearer {_auth(client)}"}
    viewer_token = client.post("/api/auth/login", json={"username": "viewer", "password": "pw"}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {viewer_token}"}
    with client.app.state.pe3_state.db.serialized() as con:
        snapshot = JobSnapshot(job_id="failed-import", owner_id=999, kind="workbook_import")
        snapshot.status = "failed"
        snapshot.error = "ValueError: invalid workbook data"
        jobs_repo.insert(con, snapshot)
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers=viewer).json() == []
    response = client.get("/api/jobs?limit=20", headers=admin)
    assert response.status_code == 200
    assert response.json()[0]["error"] == "ValueError: invalid workbook data"
    assert client.get("/api/jobs/failed-import", headers=viewer).status_code == 404
    assert client.get("/api/jobs/failed-import", headers=admin).status_code == 200
    assert client.get("/api/jobs?limit=51", headers=admin).status_code == 400
    jobs.shutdown()
