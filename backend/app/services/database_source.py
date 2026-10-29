"""Next-startup web database selection; never mutates a live DbManager."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Lock

import duckdb


_config_lock = Lock()


class InvalidDatabaseSource(ValueError):
    pass


def web_config_path() -> Path:
    override = os.getenv("PE3_WEB_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
    return root / "data" / "web-config.json"


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InvalidDatabaseSource(f"Local web configuration cannot be read: {path}") from exc
    if not isinstance(data, dict):
        raise InvalidDatabaseSource("Local web configuration must be a JSON object")
    return data


def configured_path(path: Path) -> Path | None:
    raw = _read(path).get("db_path")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidDatabaseSource("Configured database path must be a non-empty string")
    return _path(raw)


def _path(raw: str) -> Path:
    value = raw.strip()
    if not value or "://" in value or value.lower().startswith(("http:", "https:")):
        raise InvalidDatabaseSource("Enter an absolute filesystem path to an existing .duckdb file, not a URL")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() or candidate.suffix.lower() != ".duckdb":
        raise InvalidDatabaseSource("Database path must be absolute and end in .duckdb")
    return candidate.resolve()


def validate_database_path(raw: str, *, active_path: Path) -> Path:
    candidate = _path(raw)
    if not candidate.is_file():
        raise InvalidDatabaseSource("Database file does not exist or is not a regular file")
    if candidate != active_path.resolve():
        try:
            con = duckdb.connect(str(candidate), read_only=True)
            try:
                con.execute("SELECT 1").fetchone()
            finally:
                con.close()
        except Exception as exc:
            raise InvalidDatabaseSource(
                "Database could not be opened read-only. Check the file, access permissions, and other PE3 processes"
            ) from exc
    return candidate


def save_next_path(config_file: Path, raw: str, *, active_path: Path) -> Path:
    candidate = validate_database_path(raw, active_path=active_path)
    with _config_lock:
        data = _read(config_file)
        data["db_path"] = str(candidate)
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix="web-config-", suffix=".tmp", dir=config_file.parent)
            temporary = Path(temp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2)
                    stream.write("\n")
                temporary.replace(config_file)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise InvalidDatabaseSource("Local web configuration could not be saved; check its directory permissions") from exc
    return candidate
