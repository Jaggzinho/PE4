"""One-off cleanup: wipe lots/test results and import history.

Keeps master data (materials, components, component_types, properties,
material_component_defaults, tolerances, rating rules/weights, users/roles,
settings, contacts, email_templates). Wipes tests, measurements,
test_component_lots, sample queue/requests, sinottico_items and import_jobs.

Runs in one transaction; either everything is removed or nothing changes.
Backs up the database first.

Usage: python tools/wipe_test_results.py [db_path]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import duckdb

RESULTS_TABLES = [
    "measurements",
    "test_component_lots",
    "sample_request_queue",
    "sample_requests",
    "sinottico_items",
    "tests",
    "import_jobs",
]


def count(con, table: str) -> int:
    try:
        return int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
    except Exception:
        return -1


def main() -> None:
    db_path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "pe3.duckdb")
    db_path = db_path.resolve()

    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.parent / f"pe3.duckdb.wipe-backup-{stamp}.duckdb"
    shutil.copy2(db_path, backup)
    print(f"Backup written: {backup}")

    con = duckdb.connect(str(db_path))
    try:
        before = {t: count(con, t) for t in RESULTS_TABLES}
        print("Before:", before)

        # Phase 1: children and import history (DuckDB does not free FK checks
        # for child rows deleted in the same transaction as the parent, so the
        # tests delete must happen after these are committed).
        con.execute("BEGIN TRANSACTION")
        for table in RESULTS_TABLES:
            if table == "tests":
                continue
            try:
                con.execute(f"DELETE FROM {table}")
            except Exception as exc:
                con.execute("ROLLBACK")
                raise SystemExit(f"DELETE {table} failed; rolled back: {exc}") from exc
        con.execute("COMMIT")
        print("Phase 1 committed (children, history).")

        # Phase 2: parents.
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute("DELETE FROM tests")
        except Exception as exc:
            con.execute("ROLLBACK")
            raise SystemExit(f"DELETE tests failed; rolled back: {exc}") from exc
        after = {t: count(con, t) for t in RESULTS_TABLES}
        print("After (uncommitted):", after)
        missing = [t for t, n in after.items() if n != 0]
        if missing:
            con.execute("ROLLBACK")
            raise SystemExit(f"Non-empty after delete: {missing}; rolled back")
        kept = {t: count(con, t) for t in ("materials", "components", "component_types", "properties", "users", "roles")}
        print("Kept master data:", kept)
        con.execute("COMMIT")
        print("Committed. Results wiped.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
