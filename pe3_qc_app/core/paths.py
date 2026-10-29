from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from pathlib import PureWindowsPath


@dataclass(frozen=True)
class AppPaths:
    app_dir: Path
    data_dir: Path
    db_path: Path
    db_source: str  # "cli" | "config" | "default"
    subsidiary_id: str


def resolve_paths(*, db_override: str | None, subsidiary_id: str) -> AppPaths:
    from pe3_qc_app.core.local_config import get_db_path_override_for
    from pe3_qc_app.core.local_config import get_db_distribution_for
    from pe3_qc_app.core.subsidiaries import default_db_filename, normalize_subsidiary_id

    subsidiary_id = normalize_subsidiary_id(subsidiary_id)

    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent.parent.parent

    if _is_writable_dir(app_dir):
        data_dir = app_dir
    else:
        local = _local_appdata_dir() / "PE3"
        local.mkdir(parents=True, exist_ok=True)
        data_dir = local

    if db_override:
        db_path = Path(db_override).expanduser().resolve()
        db_source = "cli"
    else:
        dist = get_db_distribution_for(subsidiary_id=subsidiary_id)
        if dist is not None and dist.get("mode") == "onedrive_sync":
            source_path = Path(str(dist.get("source_path"))).expanduser()
            cache_dir = data_dir / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / source_path.name

            if source_path.exists():
                _atomic_copy_file(source_path, cache_path)
                db_path = cache_path
                db_source = "distribution_cache"
            elif cache_path.exists():
                db_path = cache_path
                db_source = "distribution_cache"
            else:
                db_path = cache_path
                db_source = "distribution_cache"
        else:
            cfg_override = get_db_path_override_for(subsidiary_id=subsidiary_id)
            if cfg_override:
                db_path = Path(cfg_override).expanduser().resolve()
                db_source = "config"
            else:
                default_name = default_db_filename(subsidiary_id=subsidiary_id)
                db_path = data_dir / default_name

                # Back-compat: older installs used `qc.duckdb` for TCM Romania.
                if subsidiary_id == "tcm_ro":
                    legacy = data_dir / "qc.duckdb"
                    if legacy.exists() and not db_path.exists():
                        db_path = legacy
                db_source = "default"

    return AppPaths(
        app_dir=app_dir,
        data_dir=data_dir,
        db_path=db_path,
        db_source=db_source,
        subsidiary_id=subsidiary_id,
    )


def allow_missing_db_autocreate(paths: AppPaths) -> bool:
    """
    Allow silently creating a brand-new DB only when it's safe.

    Use case: for TCM Romania, some deployments still use a local `qc.duckdb`
    in the app's data directory. When users delete it to "start from 0",
    DuckDB should be allowed to create a new empty file automatically.
    """
    if str(getattr(paths, "subsidiary_id", "") or "") != "tcm_ro":
        return False
    if str(getattr(paths, "db_source", "") or "") not in ("cli", "config"):
        return False

    db_path_raw = str(getattr(paths, "db_path", "") or "")
    data_dir_raw = str(getattr(paths, "data_dir", "") or "")
    if not db_path_raw or not data_dir_raw:
        return False

    # Normalize extended-length local paths (\\?\C:\...) before checking UNC-ness.
    raw_l = db_path_raw.lower()
    if raw_l.startswith("\\\\?\\"):
        db_path_raw = db_path_raw[4:]

    db_pw = PureWindowsPath(db_path_raw)
    data_pw = PureWindowsPath(data_dir_raw)

    # Reject UNC/SMB paths like \\server\share\file.duckdb
    if str(db_pw.drive).startswith("\\\\"):
        return False

    # Only allow when the DB is inside the app-managed data directory.
    try:
        return db_pw.is_relative_to(data_pw)
    except Exception:
        return False


def _local_appdata_dir() -> Path:
    p = os.environ.get("LOCALAPPDATA")
    if p:
        return Path(p).expanduser().resolve()
    return Path.home().resolve() / "AppData" / "Local"


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _atomic_copy_file(src: Path, dst: Path) -> None:
    """
    Copy a file to dst using a temp file + rename to avoid consumers seeing partial writes.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=dst.name, suffix=".tmp", dir=str(dst.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            with open(src, "rb") as rf:
                shutil.copyfileobj(rf, f, length=1024 * 1024)
        tmp_path.replace(dst)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
