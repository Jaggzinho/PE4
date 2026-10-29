from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.security import JwtSettings, decode_access_token
from backend.app.jobs.manager import JobManager
from pe3_qc_app.core.context import Session
from pe3_qc_app.db.db_manager import DbManager
from pe3_qc_app.db.migrations import apply_migrations


@dataclass(frozen=True)
class AppState:
    db: DbManager
    jwt: JwtSettings
    subsidiary_id: str
    setup_token: str | None
    jobs: object | None = None
    max_import_bytes: int = 50 * 1024 * 1024
    db_source: str = "environment"
    web_config_path: Path | None = None


def get_state(request: Request) -> AppState:
    state = getattr(request.app.state, "pe3_state", None)
    if not isinstance(state, AppState):
        raise RuntimeError("App state not initialized")
    return state


def get_jwt_settings(state: AppState = Depends(get_state)) -> JwtSettings:
    return state.jwt


def get_db(state: AppState = Depends(get_state)) -> Iterator:
    try:
        with state.db.connect() as con:
            yield con
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def get_write_db(state: AppState = Depends(get_state)) -> Iterator:
    """Provide a serialized transaction for a complete mutation request."""
    try:
        with state.db.write() as con:
            yield con
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def get_serialized_db(state: AppState = Depends(get_state)) -> Iterator:
    """Serialize writes that DuckDB cannot perform in one FK transaction."""
    try:
        with state.db.serialized() as con:
            yield con
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


_bearer = HTTPBearer(auto_error=False)


def get_session(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    state: AppState = Depends(get_state),
) -> Session:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_access_token(creds.credentials, settings=state.jwt)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    permissions = payload.get("permissions") or {}
    if not isinstance(permissions, dict):
        permissions = {}
    return Session(
        user_id=int(payload.get("sub") or 0),
        username=str(payload.get("username") or ""),
        role_name=str(payload.get("role_name") or ""),
        permissions={str(key): bool(value) for key, value in permissions.items()},
    )


def require_permission(permission: str):
    def _dependency(session: Session = Depends(get_session)) -> Session:
        if not bool(session.permissions.get(permission)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return session

    return _dependency


def init_db(db_path: Path) -> DbManager:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = DbManager(db_path)
    with db.connect() as con:
        apply_migrations(con)
    return db


def get_job_manager(state: AppState = Depends(get_state)) -> JobManager:
    if not isinstance(state.jobs, JobManager):
        raise RuntimeError("Job manager not initialized")
    return state.jobs


__all__ = [
    "AppState",
    "get_db",
    "get_jwt_settings",
    "get_job_manager",
    "get_serialized_db",
    "get_session",
    "get_state",
    "get_write_db",
    "init_db",
    "require_permission",
]
