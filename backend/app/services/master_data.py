from __future__ import annotations

import math

from pe3_qc_app.db.repos.component_types_repo import (
    delete_component_type,
    list_component_types,
    upsert_component_type,
)
from pe3_qc_app.db.repos.components_repo import delete_component, list_components, upsert_component
from pe3_qc_app.db.repos.contacts_repo import delete_contact, list_contacts, upsert_contact
from pe3_qc_app.db.repos.email_templates_repo import delete_template, list_templates, upsert_template
from pe3_qc_app.db.repos.materials_repo import delete_material, get_material, list_materials, upsert_material
from pe3_qc_app.db.repos.properties_repo import delete_property, list_properties, upsert_property
from pe3_qc_app.db.repos.tolerances_repo import delete_tolerance, list_tolerances, upsert_tolerance
from pe3_qc_app.services.material_visibility import get_visible_material_ids


class MasterDataNotFoundError(LookupError):
    pass


class ToleranceValidationError(ValueError):
    pass


_BOUNDS = ("warn_low", "warn_high", "alarm_low", "alarm_high")


def _resolved_tolerance(payload) -> tuple[dict, dict]:
    """Resolve user inputs to effective numeric limits for existing consumers."""
    configured = "reference_value" in payload.model_fields_set or any(
        f"{bound}_input" in payload.model_fields_set for bound in _BOUNDS
    )
    reference = payload.reference_value
    if reference is not None and not math.isfinite(reference):
        raise ToleranceValidationError("Reference must be finite.")
    effective: dict[str, float | None] = {}
    inputs: dict[str, float | str | None] = {"reference_value": reference}
    for bound in _BOUNDS:
        mode = getattr(payload, f"{bound}_mode")
        value = getattr(payload, f"{bound}_input") if configured else getattr(payload, bound)
        if value is not None and not math.isfinite(value):
            raise ToleranceValidationError(f"{bound} must be finite.")
        if mode == "percent" and value is not None:
            if reference is None or reference == 0:
                raise ToleranceValidationError("A nonzero reference is required for percentage tolerances.")
            if value < 0:
                raise ToleranceValidationError("Percentage deviations must be nonnegative.")
            delta = abs(reference) * value / 100.0
            result = reference - delta if bound.endswith("low") else reference + delta
        else:
            result = value
        if result is not None and not math.isfinite(result):
            raise ToleranceValidationError(f"{bound} is out of range.")
        effective[bound] = result
        inputs[f"{bound}_input"] = value
        inputs[f"{bound}_mode"] = mode if configured else "absolute"
    if configured and all(value is None for value in effective.values()):
        raise ToleranceValidationError("Enter at least one tolerance limit.")
    for low, high in (("warn_low", "warn_high"), ("alarm_low", "alarm_high")):
        if effective[low] is not None and effective[high] is not None and effective[low] > effective[high]:
            raise ToleranceValidationError(f"{low} must not exceed {high}.")
    if effective["warn_low"] is not None and effective["alarm_low"] is not None and effective["warn_low"] < effective["alarm_low"]:
        raise ToleranceValidationError("Warning minimum must be inside the alarm limits.")
    if effective["warn_high"] is not None and effective["alarm_high"] is not None and effective["warn_high"] > effective["alarm_high"]:
        raise ToleranceValidationError("Warning maximum must be inside the alarm limits.")
    if reference is not None:
        for bound in ("warn_low", "alarm_low"):
            if effective[bound] is not None and effective[bound] > reference:
                raise ToleranceValidationError("Reference must be within the configured limits.")
        for bound in ("warn_high", "alarm_high"):
            if effective[bound] is not None and effective[bound] < reference:
                raise ToleranceValidationError("Reference must be within the configured limits.")
    return effective, inputs


def _find(rows, attribute: str, value: int):
    row = next((item for item in rows if int(getattr(item, attribute)) == int(value)), None)
    if row is None:
        raise MasterDataNotFoundError
    return row


class MasterDataService:
    def materials(self, con, *, subsidiary_id: str):
        visible = get_visible_material_ids(con, subsidiary_id=subsidiary_id)
        return [row for row in list_materials(con) if int(row.material_id) in visible]

    def save_material(self, con, *, material_id: int | None, payload):
        if material_id is not None and get_material(con, material_id=material_id) is None:
            raise MasterDataNotFoundError
        saved_id = upsert_material(
            con,
            material_id=material_id,
            code=payload.code,
            description=payload.description,
            lastrina_code=payload.lastrina_code,
            lastrina_desc=payload.lastrina_desc,
            active=bool(payload.active),
        )
        row = get_material(con, material_id=saved_id)
        if row is None:
            raise MasterDataNotFoundError
        return row

    def delete_material(self, con, *, material_id: int) -> None:
        if get_material(con, material_id=material_id) is None:
            raise MasterDataNotFoundError
        delete_material(con, material_id=material_id)

    def contacts(self, con):
        return list_contacts(con)

    def save_contact(self, con, *, contact_id: int | None, payload):
        if contact_id is not None:
            _find(list_contacts(con), "contact_id", contact_id)
        saved_id = upsert_contact(
            con,
            contact_id=contact_id,
            name=payload.name,
            email=payload.email,
            group_name=payload.group_name,
            active=bool(payload.active),
        )
        return _find(list_contacts(con), "contact_id", saved_id)

    def delete_contact(self, con, *, contact_id: int) -> None:
        _find(list_contacts(con), "contact_id", contact_id)
        delete_contact(con, contact_id=contact_id)

    def templates(self, con):
        return list_templates(con)

    def save_template(self, con, *, template_id: int | None, payload):
        if template_id is not None:
            _find(list_templates(con), "template_id", template_id)
        saved_id = upsert_template(
            con,
            template_id=template_id,
            name=payload.name,
            to_group=payload.to_group,
            cc_group=payload.cc_group,
            subject_tmpl=payload.subject_tmpl,
            body_tmpl=payload.body_tmpl,
            is_html=bool(payload.is_html),
            active=bool(payload.active),
        )
        return _find(list_templates(con), "template_id", saved_id)

    def delete_template(self, con, *, template_id: int) -> None:
        _find(list_templates(con), "template_id", template_id)
        delete_template(con, template_id=template_id)

    def component_types(self, con):
        return list_component_types(con)

    def save_component_type(self, con, *, type_id: int | None, payload):
        if type_id is not None:
            _find(list_component_types(con), "type_id", type_id)
        saved_id = upsert_component_type(
            con,
            type_id=type_id,
            name=payload.name,
            slot_key=payload.slot_key,
            active=bool(payload.active),
        )
        return _find(list_component_types(con), "type_id", saved_id)

    def delete_component_type(self, con, *, type_id: int) -> None:
        _find(list_component_types(con), "type_id", type_id)
        delete_component_type(con, type_id=type_id)

    def components(self, con):
        return list_components(con)

    def save_component(self, con, *, component_id: int | None, payload):
        if component_id is not None:
            _find(list_components(con), "component_id", component_id)
        saved_id = upsert_component(
            con,
            component_id=component_id,
            type_id=int(payload.type_id),
            code=payload.code,
            description=payload.description,
            unit=payload.unit,
            active=bool(payload.active),
        )
        return _find(list_components(con), "component_id", saved_id)

    def delete_component(self, con, *, component_id: int) -> None:
        _find(list_components(con), "component_id", component_id)
        delete_component(con, component_id=component_id)

    def properties(self, con):
        return list_properties(con)

    def save_property(self, con, *, property_id: int | None, payload):
        if property_id is not None:
            _find(list_properties(con), "property_id", property_id)
        saved_id = upsert_property(
            con,
            property_id=property_id,
            name=payload.name,
            unit=payload.unit,
            active=bool(payload.active),
            sort_order=payload.sort_order,
        )
        return _find(list_properties(con), "property_id", saved_id)

    def delete_property(self, con, *, property_id: int) -> None:
        _find(list_properties(con), "property_id", property_id)
        delete_property(con, property_id=property_id)

    def tolerances(self, con):
        return list_tolerances(con)

    def save_tolerance(self, con, *, tolerance_id: int | None, payload):
        existing = list_tolerances(con)
        current = _find(existing, "tolerance_id", tolerance_id) if tolerance_id is not None else None
        material_id = int(payload.material_id) if payload.material_id is not None else None
        unchanged_key = current is not None and current.property_id == int(payload.property_id) and current.material_id == material_id
        matches = [row for row in existing if row.property_id == int(payload.property_id) and row.material_id == material_id
                   and row.tolerance_id != tolerance_id]
        if not unchanged_key and matches:
            if tolerance_id is None and not any(row.is_custom for row in matches):
                # A generated chart fallback can be converted to a user tolerance.
                tolerance_id = matches[0].tolerance_id
            else:
                raise ToleranceValidationError("A tolerance already exists for this material and property.")
        effective, inputs = _resolved_tolerance(payload)
        saved_id = upsert_tolerance(
            con,
            tolerance_id=tolerance_id,
            property_id=int(payload.property_id),
            material_id=material_id,
            **effective,
            **inputs,
        )
        return _find(list_tolerances(con), "tolerance_id", saved_id)

    def delete_tolerance(self, con, *, tolerance_id: int) -> None:
        _find(list_tolerances(con), "tolerance_id", tolerance_id)
        delete_tolerance(con, tolerance_id=tolerance_id)
