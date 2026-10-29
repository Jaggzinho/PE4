from pydantic import BaseModel, Field

from backend.app.schemas.ids import ApiId


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionResponse(BaseModel):
    user_id: ApiId
    username: str
    role_name: str
    permissions: dict[str, bool]


class SetupStatusResponse(BaseModel):
    needs_setup: bool


class FirstAdminRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    password2: str = Field(min_length=1)


__all__ = ["FirstAdminRequest", "LoginRequest", "LoginResponse", "SessionResponse", "SetupStatusResponse"]
