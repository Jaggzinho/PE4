from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.charts import ChartsTolerancePctOut
from backend.app.schemas.ids import ApiId
from backend.app.schemas.validation import NonBlankStr


class RoleOut(BaseModel):
    role_id: ApiId
    name: str
    can_edit_master: bool
    can_edit_tests: bool
    can_manage_users: bool
    can_send_outlook: bool


class RoleUpsertRequest(BaseModel):
    name: NonBlankStr
    can_edit_master: bool = False
    can_edit_tests: bool = False
    can_manage_users: bool = False
    can_send_outlook: bool = False


class UserOut(BaseModel):
    user_id: ApiId
    username: str
    role_id: ApiId
    role_name: str
    active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreateRequest(BaseModel):
    username: NonBlankStr
    password: NonBlankStr
    role_id: int
    active: bool = True


class UserUpdateRequest(BaseModel):
    role_id: int
    active: bool


class ResetPasswordRequest(BaseModel):
    new_password: NonBlankStr


class ThresholdsOut(BaseModel):
    green_days: int
    yellow_days: int


class DatabaseSourceOut(BaseModel):
    active_path: str
    active_source: str
    configured_next_path: str | None
    restart_required: bool
    override_active: bool


class DatabaseSourceRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ThresholdsUpsertRequest(BaseModel):
    green_days: int = Field(ge=0)
    yellow_days: int = Field(ge=0)


class RatingRowOut(BaseModel):
    property_id: ApiId
    property_name: str
    unit: str | None
    weight: float
    rule_json: str | None


class RatingWeightUpsertRequest(BaseModel):
    weight: float = Field(ge=0.0, allow_inf_nan=False)


class RatingRuleUpsertRequest(BaseModel):
    rule_json: NonBlankStr


__all__ = [
    "ChartsTolerancePctOut",
    "RatingRowOut",
    "RatingRuleUpsertRequest",
    "RatingWeightUpsertRequest",
    "ResetPasswordRequest",
    "RoleOut",
    "RoleUpsertRequest",
    "ThresholdsOut",
    "ThresholdsUpsertRequest",
    "UserCreateRequest",
    "UserOut",
    "UserUpdateRequest",
]
