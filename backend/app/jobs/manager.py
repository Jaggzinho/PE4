from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from pe3_qc_app.db.db_manager import DbManager
from pe3_qc_app.importer.import_service import import_workbook
from backend.app.db.repositories import import_jobs as jobs_repo


JobStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass
class JobSnapshot:
    job_id: str
    owner_id: int
    kind: str
    status: JobStatus = "queued"
    progress: int = 0
    messages: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobNotFoundError(LookupError):
    pass


class JobManager:
    """Single-worker, in-process jobs suitable for the local DuckDB runtime."""

    def __init__(self, db: DbManager) -> None:
        self._db = db
        self._lock = Lock()
        self._jobs: dict[str, JobSnapshot] = {}
        with self._db.serialized() as con:
            jobs_repo.recover_interrupted(
                con, now=datetime.now(UTC),
                message="Server stopped before import completion was recorded. The outcome may be uncertain; inspect the data before retrying.",
            )
            jobs_repo.prune_terminal(con, keep=200)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pe3-jobs")

    def submit_import(self, *, owner_id: int, workbook_path: Path) -> JobSnapshot:
        snapshot = JobSnapshot(job_id=uuid4().hex, owner_id=owner_id, kind="workbook_import")
        with self._db.serialized() as con:
            jobs_repo.insert(con, snapshot)
        with self._lock:
            self._jobs[snapshot.job_id] = snapshot
        try:
            self._executor.submit(self._run_import, snapshot.job_id, Path(workbook_path))
        except RuntimeError:
            self._update(snapshot.job_id, status="failed", error="Job worker is unavailable; the import did not start.")
            raise
        return self.get(snapshot.job_id, owner_id=owner_id)

    def get(self, job_id: str, *, owner_id: int, can_manage: bool = False) -> JobSnapshot:
        with self._lock:
            snapshot = self._jobs.get(job_id)
            if snapshot is not None:
                if snapshot.owner_id != owner_id and not can_manage:
                    raise JobNotFoundError
                return JobSnapshot(**asdict(snapshot))
        with self._db.connect() as con:
            record = jobs_repo.get(con, job_id)
        if record is None or (record["owner_id"] != owner_id and not can_manage):
            raise JobNotFoundError
        return JobSnapshot(**record)

    def list_recent(self, *, owner_id: int, can_manage: bool = False, limit: int = 20) -> list[JobSnapshot]:
        with self._db.connect() as con:
            records = jobs_repo.list_recent(con, owner_id=owner_id, can_manage=can_manage, limit=min(max(limit, 1), 50))
        with self._lock:
            live = {job_id: JobSnapshot(**asdict(snapshot)) for job_id, snapshot in self._jobs.items()}
        return [live.get(row["job_id"], JobSnapshot(**row)) for row in records]

    def shutdown(self) -> None:
        # Imports are transactional and must not be abandoned halfway through
        # application shutdown.
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _run_import(self, job_id: str, workbook_path: Path) -> None:
        def progress(message: str) -> None:
            with self._lock:
                snapshot = self._jobs[job_id]
                snapshot.messages.append(str(message))
                snapshot.progress = min(95, max(snapshot.progress, 5 + len(snapshot.messages) * 8))
                snapshot.updated_at = datetime.now(UTC)

        try:
            self._update(job_id, status="running", progress=5)
            with self._db.write() as con:
                result = import_workbook(con, workbook_path, progress)
            self._update(
                job_id,
                status="succeeded",
                progress=100,
                result={
                    "materials": int(result.materials),
                    "properties": int(result.properties),
                    "tests": int(result.tests),
                    "measurements": int(result.measurements),
                    "sinottico_items": int(result.sinottico_items),
                    "component_types": int(result.component_types),
                    "components": int(result.components),
                    "material_component_defaults": int(result.material_component_defaults),
                },
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            try:
                workbook_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            snapshot = self._jobs[job_id]
            for name, value in changes.items():
                setattr(snapshot, name, value)
            snapshot.updated_at = datetime.now(UTC)
            saved = JobSnapshot(**asdict(snapshot))
        with self._db.serialized() as con:
            jobs_repo.update(con, saved)
            if saved.status in {"succeeded", "failed"}:
                jobs_repo.prune_terminal(con, keep=200)
        if saved.status in {"succeeded", "failed"}:
            with self._lock:
                self._jobs.pop(job_id, None)
