from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb
import openpyxl

from pe3_qc_app.db.migrations import apply_migrations
from pe3_qc_app.importer.import_service import import_workbook


class TestImportMaterialiComponents(unittest.TestCase):
    def test_import_component_types_components_and_defaults(self) -> None:
        tmp = Path(tempfile.gettempdir()) / "pe3_test_import_components.xlsx"
        if tmp.exists():
            tmp.unlink()

        wb = openpyxl.Workbook()

        ws_mat = wb.active
        ws_mat.title = "materiali"
        ws_mat.append(
            [
                "codice mat",
                "desc materiale",
                "tipo comp",
                "componenti",
                "desc componenti",
                "UM",
                "cod lastrina",
                "desc last",
            ]
        )
        ws_mat.append(["MAT001", "Material 001", "ISOCIANATO", "ISO1", "Iso desc", "KG", "L001", "Las 001"])
        ws_mat.append([None, None, "POLIOLO", "POL1", "Pol desc", "KG", None, None])
        ws_mat.append([None, None, "CATALIZZATORE", "CAT1", "Cat desc", "KG", None, None])
        ws_mat.append([None, None, "ADDITIVO 3", "ADD3-1", "Additive 3 desc", "KG", None, None])

        ws_types = wb.create_sheet("TIPOLOGIE COMP")
        ws_types.append(["tipo comp"])
        for v in ["ISOCIANATO", "POLIOLO", "CATALIZZATORE", "ADDITIVO 1", "ADDITIVO 2", "EXTENDER"]:
            ws_types.append([v])

        wb.save(tmp)
        try:
            wb.close()
        except Exception:
            pass

        dbp = Path(tempfile.gettempdir()) / "pe3_test_import_components.duckdb"
        if dbp.exists():
            dbp.unlink()
        con = duckdb.connect(str(dbp))
        apply_migrations(con)
        import_workbook(con, tmp, lambda *_: None)

        slot = con.execute("SELECT slot_key FROM component_types WHERE name='ISOCIANATO'").fetchone()[0]
        self.assertEqual(str(slot), "ISO")
        slot = con.execute("SELECT slot_key FROM component_types WHERE name='POLIOLO'").fetchone()[0]
        self.assertEqual(str(slot), "POL")
        slot = con.execute("SELECT slot_key FROM component_types WHERE name='CATALIZZATORE'").fetchone()[0]
        self.assertEqual(str(slot), "CAT")

        desc = con.execute("SELECT description FROM components WHERE code='ISO1'").fetchone()[0]
        self.assertEqual(str(desc), "Iso desc")

        mid = int(con.execute("SELECT material_id FROM materials WHERE code='MAT001'").fetchone()[0])
        row = con.execute(
            """
            SELECT c.code
            FROM material_component_defaults mcd
            JOIN components c ON c.component_id = mcd.component_id
            WHERE mcd.material_id = ? AND mcd.slot_key = 'ISO'
            """,
            [mid],
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row[0]), "ISO1")
        row = con.execute(
            """
            SELECT c.code
            FROM material_component_defaults mcd
            JOIN components c ON c.component_id = mcd.component_id
            WHERE mcd.material_id = ? AND mcd.slot_key = 'ADD3'
            """,
            [mid],
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row[0]), "ADD3-1")
        con.close()


if __name__ == "__main__":
    unittest.main()

