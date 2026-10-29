from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


APP_DIRNAME = "PE3"
CONFIG_FILENAME = "config.json"
LEGACY_DB_PATH_KEY = "db_path"
DB_PATHS_BY_SUBSIDIARY_KEY = "db_paths_by_subsidiary"
DB_DISTRIBUTION_BY_SUBSIDIARY_KEY = "db_distribution_by_subsidiary"
ACTIVE_SUBSIDIARY_KEY = "active_subsidiary_id"


def get_config_dir() -> Path:
    """
    Per-machine config directory.

    Preference:
    - %PROGRAMDATA%\\PE3 (shared across Windows users)
    - %LOCALAPPDATA%\\PE3 (fallback when ProgramData is unavailable/unwritable)
    """
    candidates: list[Path] = []
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        candidates.append(Path(program_data).expanduser().resolve() / APP_DIRNAME)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata).expanduser().resolve() / APP_DIRNAME)
    candidates.append((Path.home().resolve() / "AppData" / "Local") / APP_DIRNAME)

    for p in candidates:
        if _is_writable_dir(p):
            return p
    return candidates[-1]


def load_config() -> dict[str, Any]:
    cfg_path = get_config_dir() / CONFIG_FILENAME
    if not cfg_path.exists():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(cfg: dict[str, Any]) -> None:
    p = get_config_dir()
    p.mkdir(parents=True, exist_ok=True)
    cfg_path = p / CONFIG_FILENAME
    _atomic_write_text(cfg_path, json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")


def get_db_path_override() -> str | None:
    cfg = load_config()
    raw = cfg.get(LEGACY_DB_PATH_KEY)
    if not raw:
        return None
    try:
        s = str(raw).strip()
    except Exception:
        return None
    return s or None


def set_db_path_override(db_path: Path | None) -> None:
    cfg = load_config()
    if db_path is None:
        cfg.pop(LEGACY_DB_PATH_KEY, None)
    else:
        cfg[LEGACY_DB_PATH_KEY] = str(Path(db_path).expanduser())
    save_config(cfg)


def get_active_subsidiary_id() -> str:
    from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

    cfg = load_config()
    raw = cfg.get(ACTIVE_SUBSIDIARY_KEY)
    return normalize_subsidiary_id(str(raw) if raw is not None else None)


def set_active_subsidiary_id(subsidiary_id: str) -> str:
    from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

    sid = normalize_subsidiary_id(subsidiary_id)
    cfg = load_config()
    cfg[ACTIVE_SUBSIDIARY_KEY] = sid
    save_config(cfg)
    return sid


def get_db_path_override_for(*, subsidiary_id: str) -> str | None:
    """
    Per-subsidiary DB path override stored in the local config.

    Backward compatible behavior:
    - if no per-subsidiary override exists and `subsidiary_id == 'tcm_ro'`,
      fall back to legacy `db_path`.
    """
    from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

    sid = normalize_subsidiary_id(subsidiary_id)
    cfg = load_config()
    raw_map = cfg.get(DB_PATHS_BY_SUBSIDIARY_KEY)
    if isinstance(raw_map, dict):
        raw = raw_map.get(sid)
        if raw:
            try:
                s = str(raw).strip()
            except Exception:
                s = ""
            if s:
                return s

    if sid == "tcm_ro":
        return get_db_path_override()
    return None


def set_db_path_override_for(*, subsidiary_id: str, db_path: Path | None) -> None:
    """
    Save a per-subsidiary DB path override.

    For backward compatibility, also mirrors the value to legacy `db_path`
    when saving for `tcm_ro`.
    """
    from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

    sid = normalize_subsidiary_id(subsidiary_id)
    cfg = load_config()
    raw_map = cfg.get(DB_PATHS_BY_SUBSIDIARY_KEY)
    m = raw_map if isinstance(raw_map, dict) else {}

    if db_path is None:
        m.pop(sid, None)
        if sid == "tcm_ro":
            cfg.pop(LEGACY_DB_PATH_KEY, None)
    else:
        m[sid] = str(Path(db_path).expanduser())
        if sid == "tcm_ro":
            cfg[LEGACY_DB_PATH_KEY] = m[sid]

    cfg[DB_PATHS_BY_SUBSIDIARY_KEY] = m

    # If the user explicitly configures an SMB/UNC DB path, disable any distribution mode
    # for this subsidiary to avoid confusing precedence.
    raw_dist = cfg.get(DB_DISTRIBUTION_BY_SUBSIDIARY_KEY)
    dist_map = raw_dist if isinstance(raw_dist, dict) else {}
    dist_map.pop(sid, None)
    cfg[DB_DISTRIBUTION_BY_SUBSIDIARY_KEY] = dist_map

    save_config(cfg)


def get_db_distribution_for(*, subsidiary_id: str) -> dict[str, str] | None:
    """
    Distribution mode for read-only DB snapshots.

    Stored as:
      db_distribution_by_subsidiary[sid] = {"mode": "onedrive_sync", "source_path": "..."}
    """
    from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

    sid = normalize_subsidiary_id(subsidiary_id)
    cfg = load_config()
    raw_map = cfg.get(DB_DISTRIBUTION_BY_SUBSIDIARY_KEY)
    if not isinstance(raw_map, dict):
        return None
    raw = raw_map.get(sid)
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or "").strip()
    source_path = str(raw.get("source_path") or "").strip()
    if mode != "onedrive_sync":
        return None
    if not source_path:
        return None
    return {"mode": mode, "source_path": source_path}


def set_db_distribution_for(*, subsidiary_id: str, mode: str | None, source_path: Path | None) -> None:
    """
    Set or clear distribution mode for a subsidiary.

    When set, this disables the legacy SMB/UNC db path override for the same subsidiary.
    """
    from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

    sid = normalize_subsidiary_id(subsidiary_id)
    cfg = load_config()
    raw_map = cfg.get(DB_DISTRIBUTION_BY_SUBSIDIARY_KEY)
    m = raw_map if isinstance(raw_map, dict) else {}

    if not mode or source_path is None:
        m.pop(sid, None)
    else:
        sp = str(source_path).strip()
        # Defense-in-depth: reject SharePoint/OneDrive URLs. Distribution mode expects a local
        # OneDrive-synced file path.
        sp_l = sp.lower()
        if sp_l.startswith(("http://", "https://", "http:\\", "https:\\")):
            m.pop(sid, None)
        else:
            m[sid] = {"mode": str(mode).strip(), "source_path": str(Path(source_path).expanduser())}

    cfg[DB_DISTRIBUTION_BY_SUBSIDIARY_KEY] = m

    # Disable the SMB/UNC override when distribution mode is enabled.
    raw_db_map = cfg.get(DB_PATHS_BY_SUBSIDIARY_KEY)
    db_map = raw_db_map if isinstance(raw_db_map, dict) else {}
    if sid in db_map:
        db_map.pop(sid, None)
        cfg[DB_PATHS_BY_SUBSIDIARY_KEY] = db_map
    if sid == "tcm_ro":
        cfg.pop(LEGACY_DB_PATH_KEY, None)

    save_config(cfg)


def _atomic_write_text(path: Path, text: str, *, encoding: str) -> None:
    tmp_dir = path.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(tmp_dir))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(text)
        tmp_path.replace(path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except Exception:
        return False
