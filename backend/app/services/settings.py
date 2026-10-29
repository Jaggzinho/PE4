from __future__ import annotations

from backend.app.models.domain import RatingSetting
from pe3_qc_app.db.repos.properties_repo import list_properties
from pe3_qc_app.db.repos.rating_repo import list_rules, list_weights, upsert_rule, upsert_weight
from pe3_qc_app.db.repos.roles_repo import delete_role, list_roles, upsert_role
from pe3_qc_app.db.repos.settings_repo import get_json, set_json
from pe3_qc_app.db.repos.users_repo import (
    create_user,
    delete_user,
    list_users,
    reset_password,
    update_user,
)
from pe3_qc_app.services.rating_service import validate_rule_json


class SettingsNotFoundError(LookupError):
    pass


class InvalidThresholdsError(ValueError):
    pass


def _find(rows, attribute: str, value: int):
    row = next((item for item in rows if int(getattr(item, attribute)) == int(value)), None)
    if row is None:
        raise SettingsNotFoundError
    return row


class SettingsService:
    def thresholds(self, con) -> dict[str, int]:
        value = get_json(con, "sinottico_thresholds", {"green_days": 90, "yellow_days": 180})
        return {
            "green_days": int(value.get("green_days", 90)),
            "yellow_days": int(value.get("yellow_days", 180)),
        }

    def save_thresholds(self, con, *, green_days: int, yellow_days: int) -> dict[str, int]:
        if yellow_days < green_days:
            raise InvalidThresholdsError
        value = {"green_days": int(green_days), "yellow_days": int(yellow_days)}
        set_json(con, "sinottico_thresholds", value)
        return value

    def chart_tolerance(self, con) -> dict[str, float | None]:
        value = get_json(con, "charts_tolerance_pct", {"warn_pct": 10.0, "alarm_pct": 20.0})
        return {
            "warn_pct": float(value["warn_pct"]) if value.get("warn_pct") is not None else None,
            "alarm_pct": float(value["alarm_pct"]) if value.get("alarm_pct") is not None else None,
        }

    def save_chart_tolerance(self, con, *, warn_pct: float | None, alarm_pct: float | None):
        value = {"warn_pct": warn_pct, "alarm_pct": alarm_pct}
        set_json(con, "charts_tolerance_pct", value)
        return value

    def ratings(self, con) -> list[RatingSetting]:
        weights = {row.property_id: float(row.weight) for row in list_weights(con)}
        rules = {row.property_id: row.rule_json for row in list_rules(con)}
        return [
            RatingSetting(
                property_id=prop.property_id,
                property_name=prop.name,
                unit=prop.unit,
                weight=float(weights.get(prop.property_id, 0.0)),
                rule_json=rules.get(prop.property_id),
            )
            for prop in list_properties(con)
            if prop.active
        ]

    def save_rating_weight(self, con, *, property_id: int, weight: float) -> None:
        _find(list_properties(con), "property_id", property_id)
        upsert_weight(con, property_id=property_id, weight=weight)

    def save_rating_rule(self, con, *, property_id: int, rule_json: str) -> None:
        _find(list_properties(con), "property_id", property_id)
        validate_rule_json(rule_json)
        upsert_rule(con, property_id=property_id, rule_json=rule_json)

    def roles(self, con):
        return list_roles(con)

    def save_role(self, con, *, role_id: int | None, payload):
        if role_id is not None:
            _find(list_roles(con), "role_id", role_id)
        saved_id = upsert_role(
            con,
            role_id=role_id,
            name=payload.name,
            can_edit_master=bool(payload.can_edit_master),
            can_edit_tests=bool(payload.can_edit_tests),
            can_manage_users=bool(payload.can_manage_users),
            can_send_outlook=bool(payload.can_send_outlook),
        )
        return _find(list_roles(con), "role_id", saved_id)

    def delete_role(self, con, *, role_id: int) -> None:
        _find(list_roles(con), "role_id", role_id)
        delete_role(con, role_id=role_id)

    def users(self, con):
        return list_users(con)

    def create_user(self, con, *, payload):
        user_id = create_user(
            con,
            username=payload.username,
            password=payload.password,
            role_id=int(payload.role_id),
            active=bool(payload.active),
        )
        return _find(list_users(con), "user_id", user_id)

    def update_user(self, con, *, user_id: int, payload):
        _find(list_users(con), "user_id", user_id)
        update_user(con, user_id=user_id, role_id=int(payload.role_id), active=bool(payload.active))
        return _find(list_users(con), "user_id", user_id)

    def reset_password(self, con, *, user_id: int, new_password: str) -> None:
        _find(list_users(con), "user_id", user_id)
        reset_password(con, user_id=user_id, new_password=new_password)

    def delete_user(self, con, *, user_id: int) -> None:
        _find(list_users(con), "user_id", user_id)
        delete_user(con, user_id=user_id)
