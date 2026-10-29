from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from starlette.concurrency import run_in_threadpool

from backend.app.api.deps import get_db, get_serialized_db, get_session, get_state, require_permission
from backend.app.services.database_source import InvalidDatabaseSource, configured_path, save_next_path
from backend.app.schemas.settings import (
    ChartsTolerancePctOut,
    DatabaseSourceOut,
    DatabaseSourceRequest,
    RatingRowOut,
    RatingRuleUpsertRequest,
    RatingWeightUpsertRequest,
    ResetPasswordRequest,
    RoleOut,
    RoleUpsertRequest,
    ThresholdsOut,
    ThresholdsUpsertRequest,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
)
from backend.app.services.settings import InvalidThresholdsError, SettingsNotFoundError, SettingsService
from backend.app.services.notifications import NotificationService, OutlookDraftError


router = APIRouter(prefix="/settings", tags=["settings"])
service = SettingsService()
notifications = NotificationService()
can_manage = Depends(require_permission("can_manage_users"))


def _database_source(state) -> DatabaseSourceOut:
    try:
        pending = configured_path(state.web_config_path)
    except InvalidDatabaseSource as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    active = state.db.db_path.resolve()
    return DatabaseSourceOut(
        active_path=str(active), active_source=state.db_source,
        configured_next_path=str(pending) if pending else None,
        restart_required=pending is not None and pending != active,
        override_active=state.db_source in {"command_line", "environment"},
    )


@router.get("/database-source", response_model=DatabaseSourceOut, dependencies=[can_manage])
def database_source(state=Depends(get_state)):
    return _database_source(state)


@router.put("/database-source", response_model=DatabaseSourceOut, dependencies=[can_manage])
def save_database_source(payload: DatabaseSourceRequest, state=Depends(get_state)):
    try:
        save_next_path(state.web_config_path, payload.path, active_path=state.db.db_path)
    except InvalidDatabaseSource as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _database_source(state)


@router.post("/outlook/test-draft", dependencies=[can_manage])
async def outlook_test_draft():
    try:
        await run_in_threadpool(notifications.create_outlook_test_draft)
    except OutlookDraftError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "Test draft saved and opened in Outlook. Review it before sending."}


@router.get("/outlook/test-draft.eml", dependencies=[can_manage])
def outlook_test_eml():
    return Response(
        content=notifications.as_eml(notifications.test_draft()),
        media_type="message/rfc822",
        headers={"Content-Disposition": 'attachment; filename="pe3-outlook-test.eml"'},
    )


def _not_found(call):
    try:
        return call()
    except SettingsNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _role(row) -> RoleOut:
    return RoleOut(
        role_id=row.role_id,
        name=row.name,
        can_edit_master=bool(row.can_edit_master),
        can_edit_tests=bool(row.can_edit_tests),
        can_manage_users=bool(row.can_manage_users),
        can_send_outlook=bool(row.can_send_outlook),
    )


def _user(row) -> UserOut:
    return UserOut(
        user_id=row.user_id,
        username=row.username,
        role_id=row.role_id,
        role_name=row.role_name,
        active=bool(row.active),
        created_at=row.created_at,
        last_login_at=row.last_login_at,
    )


@router.get("/thresholds", response_model=ThresholdsOut, dependencies=[can_manage])
def thresholds(con=Depends(get_db), _session=Depends(get_session)):
    return ThresholdsOut(**service.thresholds(con))


@router.put("/thresholds", response_model=ThresholdsOut, dependencies=[can_manage])
def save_thresholds(payload: ThresholdsUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    try:
        value = service.save_thresholds(
            con,
            green_days=int(payload.green_days),
            yellow_days=int(payload.yellow_days),
        )
    except InvalidThresholdsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="yellow_days must be >= green_days",
        )
    return ThresholdsOut(**value)


@router.get("/charts-tolerance-pct", response_model=ChartsTolerancePctOut, dependencies=[can_manage])
def chart_tolerance(con=Depends(get_db), _session=Depends(get_session)):
    return ChartsTolerancePctOut(**service.chart_tolerance(con))


@router.put("/charts-tolerance-pct", response_model=ChartsTolerancePctOut, dependencies=[can_manage])
def save_chart_tolerance(payload: ChartsTolerancePctOut, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return ChartsTolerancePctOut(
        **service.save_chart_tolerance(
            con,
            warn_pct=payload.warn_pct,
            alarm_pct=payload.alarm_pct,
        )
    )


@router.get("/ratings", response_model=list[RatingRowOut], dependencies=[can_manage])
def ratings(con=Depends(get_db), _session=Depends(get_session)):
    return [RatingRowOut(**row.__dict__) for row in service.ratings(con)]


@router.put("/ratings/{property_id}/weight", status_code=204, dependencies=[can_manage])
def save_rating_weight(property_id: int, payload: RatingWeightUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(
        lambda: service.save_rating_weight(
            con,
            property_id=int(property_id),
            weight=float(payload.weight),
        )
    )


@router.put("/ratings/{property_id}/rule", status_code=204, dependencies=[can_manage])
def save_rating_rule(property_id: int, payload: RatingRuleUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    try:
        _not_found(
            lambda: service.save_rating_rule(
                con,
                property_id=int(property_id),
                rule_json=str(payload.rule_json),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid rating rule JSON: {exc}") from exc


@router.get("/roles", response_model=list[RoleOut], dependencies=[can_manage])
def roles(con=Depends(get_db), _session=Depends(get_session)):
    return [_role(row) for row in service.roles(con)]


@router.post("/roles", response_model=RoleOut, dependencies=[can_manage])
def create_role(payload: RoleUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _role(service.save_role(con, role_id=None, payload=payload))


@router.put("/roles/{role_id}", response_model=RoleOut, dependencies=[can_manage])
def update_role(role_id: int, payload: RoleUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _role(_not_found(lambda: service.save_role(con, role_id=role_id, payload=payload)))


@router.delete("/roles/{role_id}", status_code=204, dependencies=[can_manage])
def remove_role(role_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_role(con, role_id=role_id))


@router.get("/users", response_model=list[UserOut], dependencies=[can_manage])
def users(con=Depends(get_db), _session=Depends(get_session)):
    return [_user(row) for row in service.users(con)]


@router.post("/users", response_model=UserOut, dependencies=[can_manage])
def create_user(payload: UserCreateRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _user(service.create_user(con, payload=payload))


@router.put("/users/{user_id}", response_model=UserOut, dependencies=[can_manage])
def update_user(user_id: int, payload: UserUpdateRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _user(_not_found(lambda: service.update_user(con, user_id=user_id, payload=payload)))


@router.post("/users/{user_id}/reset-password", status_code=204, dependencies=[can_manage])
def reset_password(user_id: int, payload: ResetPasswordRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.reset_password(con, user_id=user_id, new_password=payload.new_password))


@router.delete("/users/{user_id}", status_code=204, dependencies=[can_manage])
def remove_user(user_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_user(con, user_id=user_id))
