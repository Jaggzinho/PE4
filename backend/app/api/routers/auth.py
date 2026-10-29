from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.services.auth import (
    AlreadySetupError,
    AuthService,
    InvalidCredentialsError,
    InvalidSetupTokenError,
    PasswordMismatchError,
    SetupDisabledError,
)
from backend.app.schemas.auth import FirstAdminRequest, LoginRequest, LoginResponse, SessionResponse, SetupStatusResponse
from backend.app.api.deps import get_db, get_jwt_settings, get_session, get_state, get_write_db
from backend.app.core.security import JwtSettings, create_access_token


router = APIRouter()
service = AuthService()


@router.get("/setup/status", response_model=SetupStatusResponse)
def setup_status(con=Depends(get_db)):
    return SetupStatusResponse(needs_setup=service.needs_setup(con))


@router.post("/setup/first-admin", status_code=204)
def setup_first_admin(
    payload: FirstAdminRequest,
    x_pe3_setup_token: str | None = Header(default=None, alias="X-PE3-SETUP-TOKEN"),
    con=Depends(get_write_db),
    state=Depends(get_state),
):
    try:
        service.create_first_admin(
            con,
            configured_token=state.setup_token,
            supplied_token=x_pe3_setup_token,
            username=payload.username,
            password=payload.password,
            password_confirmation=payload.password2,
        )
    except SetupDisabledError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setup disabled")
    except InvalidSetupTokenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid setup token")
    except AlreadySetupError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already set up")
    except PasswordMismatchError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, con=Depends(get_write_db), jwt_settings: JwtSettings = Depends(get_jwt_settings)):
    try:
        session = service.login(con, username=payload.username, password=payload.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/password")
    return LoginResponse(access_token=create_access_token(session, settings=jwt_settings))


@router.get("/auth/me", response_model=SessionResponse)
def me(session=Depends(get_session)):
    return SessionResponse(
        user_id=int(session.user_id),
        username=str(session.username),
        role_name=str(session.role_name),
        permissions=dict(session.permissions or {}),
    )
