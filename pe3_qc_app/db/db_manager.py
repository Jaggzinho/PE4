from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import time
import logging
from threading import RLock

import duckdb


class DbManager:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        # DuckDB allows a single writing process.  All application writes share
        # this lock; reads continue to use independent short-lived connections.
        self._write_lock = RLock()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def write(self):
        """Yield one serialized, transactional write connection."""
        with self._write_lock:
            with self.connect() as con:
                con.execute("BEGIN TRANSACTION")
                try:
                    yield con
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
                else:
                    con.execute("COMMIT")

    @contextmanager
    def serialized(self):
        """Yield a locked autocommit connection for DuckDB FK-safe deletes."""
        with self._write_lock:
            with self.connect() as con:
                yield con

    @contextmanager
    def connect(self):
        con = None
        attempts = 10
        delay_s = 0.1
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                con = duckdb.connect(str(self._db_path))
                break
            except Exception as e:  # noqa: BLE001
                last_exc = e
                msg = str(e)
                is_locked = ("Cannot open file" in msg and "used by another process" in msg) or "Unique file handle conflict" in msg
                if not is_locked or i == attempts - 1:
                    break
                time.sleep(delay_s)

        if con is None:
            if last_exc is not None:
                log = logging.getLogger("pe3_qc_app.db")
                log.warning("DuckDB open failed (db_path=%s): %s", str(self._db_path), str(last_exc))
                raise RuntimeError(
                    f"DuckDB database is busy/locked: {self._db_path}. "
                    "Close other PE3 instances, Excel, or any process using qc.duckdb and retry."
                ) from last_exc
            raise RuntimeError(f"DuckDB database is busy/locked: {self._db_path}.")
        try:
            con.execute("PRAGMA threads=4")
            yield con
        finally:
            try:
                con.close()
            except Exception:
                pass
