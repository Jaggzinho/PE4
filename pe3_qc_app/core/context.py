from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pe3_qc_app.core.event_bus import EventBus
from pe3_qc_app.core.paths import AppPaths, resolve_paths
from pe3_qc_app.db.db_manager import DbManager


@dataclass
class Session:
    user_id: int
    username: str
    role_name: str
    permissions: dict[str, bool]


@dataclass
class AppContext:
    paths: AppPaths
    log_file: Path | None
    bus: EventBus
    db: DbManager
    session: Session | None
    selected_material_id: int | None
    ui_language: str
    dev: bool
    subsidiary_id: str

    @classmethod
    def create(cls, *, db_override: str | None, dev: bool, subsidiary_id: str | None = None) -> "AppContext":
        from pe3_qc_app.core.local_config import get_active_subsidiary_id
        from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id

        sid = normalize_subsidiary_id(subsidiary_id or get_active_subsidiary_id())
        paths = resolve_paths(db_override=db_override, subsidiary_id=sid)
        return cls(
            paths=paths,
            log_file=None,
            bus=EventBus(),
            db=DbManager(paths.db_path),
            session=None,
            selected_material_id=None,
            ui_language="it_IT",
            dev=dev,
            subsidiary_id=sid,
        )
