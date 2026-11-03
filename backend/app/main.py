from __future__ import annotations

import logging

import duckdb

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.errors import install_error_handlers
from backend.app.jobs.manager import JobManager
from backend.app.config import load_config
from backend.app.api.deps import AppState, EnvironmentState, init_db
from backend.app.db.repositories import identity
from pe3_qc_app.db.db_manager import DbManager
from backend.app.core.security import JwtSettings
from backend.app.static_spa import maybe_mount_spa
from pe3_qc_app.services.material_visibility import get_visible_material_codes


def create_app() -> FastAPI:
    config = load_config()
    db = init_db(config.db_path)
    config.auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_db = DbManager(config.auth_path)
    with db.connect() as con:
        roles, users = identity.snapshot(con)
    with auth_db.write() as con:
        identity.initialize(con, roles=roles, users=users)
    environments = {}
    try:
        for environment in config.environments:
            try:
                if environment.source == "local_config" and not environment.db_path.is_file():
                    raise RuntimeError("Configured environment database file does not exist")
                manager = db if environment.environment_id == "tcm_ro" else init_db(environment.db_path)
                # Visibility queries can lazily seed this setting. Seed under
                # the write lock before requests so ordinary GETs stay read-only.
                with manager.write() as con:
                    get_visible_material_codes(con, subsidiary_id=environment.environment_id)
                jobs = JobManager(manager)
                environments[environment.environment_id] = EnvironmentState(environment, manager, jobs)
            except (duckdb.Error, OSError, RuntimeError):
                if environment.environment_id == "tcm_ro":
                    raise
                logging.getLogger(__name__).exception("Environment unavailable: %s", environment.environment_id)
                environments[environment.environment_id] = EnvironmentState(environment, None, None)
    except Exception:
        for environment in environments.values():
            if environment.jobs is not None:
                environment.jobs.shutdown()
        raise
    app = FastAPI(title="PE3 QC Web API", version="0.2.0")
    app.state.pe3_state = AppState(
        db=db,
        jwt=JwtSettings(secret=config.jwt_secret),
        subsidiary_id="tcm_ro",
        setup_token=config.setup_token,
        jobs=environments["tcm_ro"].jobs,
        max_import_bytes=config.max_import_bytes,
        db_source=config.db_source,
        web_config_path=config.web_config_path,
        auth_db=auth_db,
        environments=environments,
        data_dir=config.data_dir,
    )
    for environment in environments.values():
        if environment.jobs is not None:
            app.router.add_event_handler("shutdown", environment.jobs.shutdown)
    install_error_handlers(app)

    # Production is single-origin. CORS is only enabled for the explicit Vite
    # origins supplied in development configuration.
    if config.dev and config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router)
    maybe_mount_spa(app)
    return app
