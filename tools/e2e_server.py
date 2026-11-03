"""Disposable built-app server for Playwright. Never opens qc.duckdb."""

from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import sys

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_web_api import _seed_db  # noqa: E402


def main() -> None:
    runtime = (ROOT / ".e2e").resolve()
    if runtime.parent != ROOT or runtime.name != ".e2e":
        raise RuntimeError("Unsafe E2E runtime path")
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir()
    active = runtime / "active.duckdb"
    next_database = runtime / "next.duckdb"
    _seed_db(str(active))
    _seed_db(str(next_database))
    # A separate QC fixture for the tolerance workflow: the workbook-import test
    # replaces Sinottico rows in TCM and must not invalidate this test's material.
    # Copy only this disposable, closed fixture; production provisioning stays empty.
    wuxi_fixture = runtime / "wuxi-fixture.duckdb"
    shutil.copy2(active, wuxi_fixture)
    (runtime / "web-config.json").write_text(
        json.dumps({"environments": {"wam_wuxi": str(wuxi_fixture)}}), encoding="utf-8",
    )
    os.environ.update({
        "PE3_DB_PATH": str(active),
        "PE3_DB_SOURCE": "environment",
        "PE3_WEB_CONFIG_PATH": str(runtime / "web-config.json"),
        "PE3_JWT_SECRET": "playwright-secret-at-least-32-characters-long",
        "PE3_STATIC_DIR": str((ROOT / "dist").resolve()),
        "PE3_CORS_ORIGINS": "",
        "PE3_SETUP_TOKEN": "",
        "PE3_SUBSIDIARY_ID": "tcm_ro",
        "PE3_DATA_DIR": str(runtime),
        "PE3_AUTH_DB_PATH": str(runtime / "auth.duckdb"),
        "PE3_DISABLE_OUTLOOK_COM": "1",
    })
    uvicorn.run("backend.app.main:create_app", factory=True, host="127.0.0.1", port=8765, workers=1, log_level="warning")


if __name__ == "__main__":
    main()
