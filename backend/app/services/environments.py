"""Server-owned environment registry; client IDs are never filesystem paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pe3_qc_app.core.subsidiaries import SUBSIDIARIES
from backend.app.services.database_source import _read, _path


@dataclass(frozen=True)
class EnvironmentConfig:
    environment_id: str
    label: str
    flag_key: str
    db_path: Path
    source: str


def same_file(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and left.samefile(right)
    )


def load_environments(*, config_file: Path, current_path: Path, current_source: str,
                      data_dir: Path, auth_path: Path) -> tuple[EnvironmentConfig, ...]:
    saved = _read(config_file).get("environments", {})
    if not isinstance(saved, dict) or set(saved) - {s.subsidiary_id for s in SUBSIDIARIES}:
        raise ValueError("Invalid environment registry")
    if "tcm_ro" in saved:
        raise ValueError("Configure TCM Romania with db_path, not environments.tcm_ro")
    result = []
    for subsidiary in SUBSIDIARIES:
        sid = subsidiary.subsidiary_id
        if sid == "tcm_ro":
            path, source = current_path, current_source
        elif sid in saved:
            if not isinstance(saved[sid], str):
                raise ValueError(f"Invalid environment database path: {sid}")
            path, source = _path(saved[sid]), "local_config"
        else:
            path, source = data_dir / "environments" / sid / "qc.duckdb", "default"
        if same_file(path, auth_path) or any(same_file(path, item.db_path) for item in result):
            raise ValueError("Each environment and the shared login store require distinct database files")
        result.append(EnvironmentConfig(sid, subsidiary.label, subsidiary.flag_key, path, source))
    return tuple(result)
