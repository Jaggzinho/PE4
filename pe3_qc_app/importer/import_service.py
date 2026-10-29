from __future__ import annotations

from pathlib import Path
from typing import Callable

import openpyxl

from pe3_qc_app.importer.import_components import import_components
from pe3_qc_app.importer.import_materials import import_materials
from pe3_qc_app.importer.import_models import ImportResult
from pe3_qc_app.importer.import_sinottico import import_sinottico
from pe3_qc_app.importer.import_tabella1 import import_tabella1
from pe3_qc_app.db.repos.tests_repo import backfill_test_component_descriptions


def import_workbook(con, xlsm_path: Path, progress: Callable[[str], None]) -> ImportResult:
    progress(f"Loading workbook: {xlsm_path}")
    wb = openpyxl.load_workbook(str(xlsm_path), data_only=True, keep_vba=True)
    try:
        mats = import_materials(con, wb, progress)
        ct, comps, defs = import_components(con, wb, progress)
        tests, meas, props = import_tabella1(con, wb, progress)
        fixed = backfill_test_component_descriptions(con)
        if fixed:
            progress(f"Backfilled component descriptions: {fixed}")
        sin = import_sinottico(con, wb, progress)
        progress("Import complete.")
        return ImportResult(
            materials=mats,
            properties=props,
            tests=tests,
            measurements=meas,
            sinottico_items=sin,
            component_types=ct,
            components=comps,
            material_component_defaults=defs,
        )
    finally:
        try:
            wb.close()
        except Exception:
            pass
