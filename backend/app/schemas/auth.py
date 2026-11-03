from pydantic import BaseModel, Field

from backend.app.schemas.ids import ApiId


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    # Compatibility for existing local API clients; the UI always sends a choice.
    environment_id: str = "tcm_ro"


class EnvironmentOut(BaseModel):
    environment_id: str
    label: str
    flag_key: str
    available: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionResponse(BaseModel):
    user_id: ApiId
    username: str
    role_name: str
    permissions: dict[str, bool]
    environment: EnvironmentOut


class SetupStatusResponse(BaseModel):
    needs_setup: bool


class FirstAdminRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    password2: str = Field(min_length=1)


__all__ = ["FirstAdminRequest", "LoginRequest", "LoginResponse", "SessionResponse", "SetupStatusResponse"]
