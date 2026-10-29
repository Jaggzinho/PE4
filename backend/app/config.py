"""Configuration compatibility module for the target backend package."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from backend.app.services.database_source import configured_path, web_config_path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class WebConfig:
    db_path: Path
    db_source: str
    web_config_path: Path
    jwt_secret: str
    cors_origins: list[str]
    dev: bool
    subsidiary_id: str
    setup_token: str | None
    max_import_bytes: int


def load_config() -> WebConfig:
    db_path_raw = (os.getenv("PE3_DB_PATH") or "").strip()
    local_config_file = web_config_path()
    if db_path_raw:
        db_path = Path(db_path_raw).expanduser().resolve()
        db_source = (os.getenv("PE3_DB_SOURCE") or "environment").strip()
    else:
        db_path = configured_path(local_config_file)
        if db_path is None:
            raise RuntimeError("Missing PE3_DB_PATH and no local web database path is configured")
        if not db_path.is_file():
            raise RuntimeError(f"Configured database file does not exist: {db_path}")
        db_source = "local_config"

    jwt_secret = (os.getenv("PE3_JWT_SECRET") or "").strip()
    if not jwt_secret:
        raise RuntimeError("Missing required env var: PE3_JWT_SECRET (JWT signing secret)")

    origins_raw = (os.getenv("PE3_CORS_ORIGINS") or "").strip()
    cors_origins = [origin.strip().rstrip("/") for origin in origins_raw.split(",") if origin.strip()]
    dev = _env_bool("PE3_DEV", default=False)
    subsidiary_id = (os.getenv("PE3_SUBSIDIARY_ID") or "tcm_ro").strip() or "tcm_ro"
    setup_token_raw = (os.getenv("PE3_SETUP_TOKEN") or "").strip()
    setup_token = setup_token_raw if setup_token_raw else None
    max_import_bytes = int(os.getenv("PE3_MAX_IMPORT_BYTES") or 50 * 1024 * 1024)
    if max_import_bytes <= 0:
        raise RuntimeError("PE3_MAX_IMPORT_BYTES must be greater than zero")

    return WebConfig(
        db_path=db_path,
        db_source=db_source,
        web_config_path=local_config_file,
        jwt_secret=jwt_secret,
        cors_origins=cors_origins,
        dev=dev,
        subsidiary_id=subsidiary_id,
        setup_token=setup_token,
        max_import_bytes=max_import_bytes,
    )


__all__ = ["WebConfig", "load_config"]
