from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.tests_repo import backfill_test_component_descriptions
from pe3_qc_app.services.time_utils import utc_now_naive


class TestBackfillComponentDesc(unittest.TestCase):
    def test_backfill_fills_missing_desc_only(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_backfill_comp_desc.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

        type_id = new_id()
        con.execute("INSERT INTO component_types(type_id, name, slot_key, active) VALUES (?, 'ISOCIANATO', 'ISO', TRUE)", [int(type_id)])
        con.execute(
            "INSERT INTO components(component_id, type_id, code, description, unit, active) VALUES (?, ?, 'ISO1', 'Iso desc', NULL, TRUE)",
            [int(new_id()), int(type_id)],
        )

        mid = new_id()
        con.execute(
            """
            INSERT INTO materials(material_id, code, description, lastrina_code, lastrina_desc, system_name, machine_name, active)
            VALUES (?, 'MAT001', 'Material 001', NULL, NULL, NULL, NULL, TRUE)
            """,
            [int(mid)],
        )
        test_id = new_id()
        con.execute(
            """
            INSERT INTO tests(
                test_id, material_id, request_date, prod_date, analysis_date,
                notes, created_by, created_at, deleted_at, external_source, external_row_key
            )
            VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, ?, NULL, 'Manual', ?)
            """,
            [int(test_id), int(mid), utc_now_naive(), str(int(test_id))],
        )
        con.execute(
            "INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code) VALUES (?, 'ISO', 'ISO1', NULL, 'L')",
            [int(test_id)],
        )
        con.execute(
            "INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code) VALUES (?, 'POL', 'X', 'Already', 'L')",
            [int(test_id)],
        )

        backfill_test_component_descriptions(con)

        d1 = con.execute(
            "SELECT component_desc FROM test_component_lots WHERE test_id=? AND type_name='ISO'",
            [int(test_id)],
        ).fetchone()[0]
        self.assertEqual(str(d1), "Iso desc")

        d2 = con.execute(
            "SELECT component_desc FROM test_component_lots WHERE test_id=? AND type_name='POL'",
            [int(test_id)],
        ).fetchone()[0]
        self.assertEqual(str(d2), "Already")
        con.close()

    def test_backfill_inside_transaction_keeps_transaction_usable(self) -> None:
        """Regression: imports run inside a write transaction; a failing
        statement (DuckDB removed SELECT changes()) used to abort the
        transaction and every later import statement failed with
        "Current transaction is aborted (please ROLLBACK)"."""
        dbp = Path(tempfile.gettempdir()) / "pe3_test_backfill_in_txn.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

        type_id = new_id()
        con.execute("INSERT INTO component_types(type_id, name, slot_key, active) VALUES (?, 'ISOCIANATO', 'ISO', TRUE)", [int(type_id)])
        con.execute(
            "INSERT INTO components(component_id, type_id, code, description, unit, active) VALUES (?, ?, 'ISO1', 'Iso desc', NULL, TRUE)",
            [int(new_id()), int(type_id)],
        )
        mid = new_id()
        con.execute(
            "INSERT INTO materials(material_id, code, description, active) VALUES (?, 'MAT001', 'Material 001', TRUE)",
            [int(mid)],
        )
        test_id = new_id()
        con.execute(
            """
            INSERT INTO tests(
                test_id, material_id, request_date, prod_date, analysis_date,
                notes, created_by, created_at, deleted_at, external_source, external_row_key
            )
            VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, ?, NULL, 'Manual', ?)
            """,
            [int(test_id), int(mid), utc_now_naive(), str(int(test_id))],
        )
        con.execute(
            "INSERT INTO test_component_lots(test_id, type_name, component_code, component_desc, lot_code) VALUES (?, 'ISO', 'ISO1', NULL, 'L')",
            [int(test_id)],
        )

        con.execute("BEGIN TRANSACTION")
        fixed = backfill_test_component_descriptions(con)
        self.assertEqual(int(fixed), 1)
        # The transaction must still be usable after the backfill.
        con.execute("DELETE FROM sinottico_items")
        con.execute("COMMIT")

        d1 = con.execute(
            "SELECT component_desc FROM test_component_lots WHERE test_id=? AND type_name='ISO'",
            [int(test_id)],
        ).fetchone()[0]
        self.assertEqual(str(d1), "Iso desc")
        con.close()


if __name__ == "__main__":
    unittest.main()

