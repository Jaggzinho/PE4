from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from fastapi.testclient import TestClient

from backend.app.core.security import JwtSettings, create_access_token
from backend.app.main import create_app
from pe3_qc_app.core.context import Session
from pe3_qc_app.db.db_manager import DbManager


JWT_SECRET = "cutover-validation-secret-at-least-32-characters"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _session_from_copy(db_path: Path) -> Session:
    manager = DbManager(db_path)
    with manager.connect() as connection:
        row = connection.execute(
            """
            SELECT u.user_id, u.username, r.name,
                   r.can_edit_master, r.can_edit_tests,
                   r.can_manage_users, r.can_send_outlook
            FROM users u
            JOIN roles r ON r.role_id = u.role_id
            WHERE u.active = TRUE
            ORDER BY r.can_manage_users DESC, r.can_edit_master DESC, u.user_id
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise RuntimeError("The database copy has no active user for authenticated validation")
    return Session(
        user_id=int(row[0]),
        username=str(row[1]),
        role_name=str(row[2]),
        permissions={
            "can_edit_master": bool(row[3]),
            "can_edit_tests": bool(row[4]),
            "can_manage_users": bool(row[5]),
            "can_send_outlook": bool(row[6]),
        },
    )


def _get_json(client: TestClient, path: str, headers: dict[str, str]):
    response = client.get(path, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"GET {path} failed: {response.status_code} {response.text}")
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise RuntimeError(f"GET {path} did not return JSON")
    return response.json()


def validate(source: Path, static_dir: Path) -> dict[str, object]:
    source = source.resolve()
    static_dir = static_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    wal_path = Path(f"{source}.wal")
    if wal_path.exists():
        raise RuntimeError(f"Refusing to copy a database with an active WAL file: {wal_path}")
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(static_dir / "index.html")

    source_hash = _sha256(source)
    with tempfile.TemporaryDirectory(prefix="pe3-cutover-") as temp:
        copy_path = Path(temp) / source.name
        shutil.copy2(source, copy_path)
        os.environ.update(
            {
                "PE3_DB_PATH": str(copy_path),
                "PE3_JWT_SECRET": JWT_SECRET,
                "PE3_STATIC_DIR": str(static_dir),
                "PE3_CORS_ORIGINS": "",
                "PE3_DEV": "0",
            }
        )
        session = _session_from_copy(copy_path)
        token = create_access_token(session, settings=JwtSettings(secret=JWT_SECRET))
        headers = {"Authorization": f"Bearer {token}"}
        summary: dict[str, object] = {}

        with TestClient(create_app()) as client:
            root = client.get("/")
            if root.status_code != 200 or "text/html" not in root.headers.get("content-type", ""):
                raise RuntimeError("Built SPA is not served at /")
            missing = client.get("/api/cutover-route-that-does-not-exist")
            if missing.status_code != 404 or missing.json().get("code") != "not_found":
                raise RuntimeError("Unknown API routes are not returning structured JSON 404 responses")

            _get_json(client, "/api/health", {})
            _get_json(client, "/api/auth/me", headers)
            sinottico = _get_json(client, "/api/sinottico", headers)
            lots = _get_json(client, "/api/lots?limit=25", headers)
            materials = _get_json(client, "/api/materials", headers)
            today = date.today()
            calendar = _get_json(
                client,
                f"/api/calendar?year={today.year}&month={today.month}",
                headers,
            )
            _get_json(client, "/api/charts/config", headers)

            id_samples = [
                *(row.get("item_id") for row in sinottico[:1]),
                *(row.get("test_id") for row in lots[:1]),
                *(row.get("material_id") for row in materials[:1]),
            ]
            if any(not isinstance(value, str) or not value.isdecimal() for value in id_samples):
                raise RuntimeError("API identifiers are not lossless decimal strings")

            if materials:
                material_id = int(materials[0]["material_id"])
                _get_json(client, f"/api/charts/panels?material_id={material_id}", headers)
                _get_json(client, f"/api/ratings?material_id={material_id}", headers)

            if session.permissions["can_edit_master"]:
                _get_json(client, "/api/master-data/materials", headers)
                _get_json(client, "/api/master-data/tolerances", headers)
            if session.permissions["can_manage_users"]:
                _get_json(client, "/api/settings/thresholds", headers)
                _get_json(client, "/api/settings/users", headers)

            summary.update(
                {
                    "user": session.username,
                    "sinottico_rows": len(sinottico),
                    "lot_rows_sampled": len(lots),
                    "visible_materials": len(materials),
                    "calendar_items": len(calendar.get("items", [])),
                    "source_unchanged": _sha256(source) == source_hash,
                }
            )

    if not summary["source_unchanged"]:
        raise RuntimeError("Source database changed during copy validation")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the production web cutover against a database copy.")
    parser.add_argument("db", type=Path, help="Source DuckDB file; it is copied and never opened by PE3.")
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "dist",
        help="Built frontend directory (default: repository dist/).",
    )
    args = parser.parse_args()
    print(json.dumps(validate(args.db, args.static_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
