from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.errors import install_error_handlers
from backend.app.jobs.manager import JobManager
from backend.app.config import load_config
from backend.app.api.deps import AppState, init_db
from backend.app.core.security import JwtSettings
from backend.app.static_spa import maybe_mount_spa


def create_app() -> FastAPI:
    config = load_config()
    db = init_db(config.db_path)
    jobs = JobManager(db)
    app = FastAPI(title="PE3 QC Web API", version="0.2.0")
    app.state.pe3_state = AppState(
        db=db,
        jwt=JwtSettings(secret=config.jwt_secret),
        subsidiary_id=config.subsidiary_id,
        setup_token=config.setup_token,
        jobs=jobs,
        max_import_bytes=config.max_import_bytes,
        db_source=config.db_source,
        web_config_path=config.web_config_path,
    )
    app.router.add_event_handler("shutdown", jobs.shutdown)
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
