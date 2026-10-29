from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from pe3_qc_app.db.ids import new_id
from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.db.repos.tests_repo import upsert_component_lot
from pe3_qc_app.services.time_utils import utc_now_naive


class TestComponentDescBinding(unittest.TestCase):
    def test_upsert_component_lot_binds_desc_from_master_data(self) -> None:
        dbp = Path(tempfile.gettempdir()) / "pe3_test_comp_desc_bind.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)

        type_id = new_id()
        con.execute(
            "INSERT INTO component_types(type_id, name, slot_key, active) VALUES (?, 'ISOCIANATO', 'ISO', TRUE)",
            [int(type_id)],
        )
        comp_id = new_id()
        con.execute(
            """
            INSERT INTO components(component_id, type_id, code, description, unit, active)
            VALUES (?, ?, 'ISO1', 'Iso desc', 'KG', TRUE)
            """,
            [int(comp_id), int(type_id)],
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

        upsert_component_lot(
            con,
            test_id=int(test_id),
            type_name="ISO",
            component_code="ISO1",
            component_desc=None,
            lot_code="LOT1",
        )
        row = con.execute(
            "SELECT component_desc FROM test_component_lots WHERE test_id=? AND type_name='ISO'",
            [int(test_id)],
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row[0]), "Iso desc")
        con.close()


if __name__ == "__main__":
    unittest.main()

