from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_db, get_serialized_db, get_session, get_state, require_permission
from backend.app.schemas.master_data import (
    ComponentOut,
    ComponentTypeOut,
    ComponentTypeUpsertRequest,
    ComponentUpsertRequest,
    ContactOut,
    ContactUpsertRequest,
    EmailTemplateOut,
    EmailTemplateUpsertRequest,
    MaterialOut,
    MaterialUpsertRequest,
    PropertiesOut,
    PropertyUpsertRequest,
    ToleranceOut,
    ToleranceUpsertRequest,
)
from backend.app.services.master_data import MasterDataNotFoundError, MasterDataService, ToleranceValidationError


router = APIRouter(prefix="/master-data", tags=["master-data"])
service = MasterDataService()
can_edit = Depends(require_permission("can_edit_master"))


def _not_found(call):
    try:
        return call()
    except MasterDataNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _material(row) -> MaterialOut:
    return MaterialOut(
        material_id=row.material_id,
        code=row.code,
        description=row.description,
        lastrina_code=row.lastrina_code,
        lastrina_desc=row.lastrina_desc,
        active=bool(row.active),
    )


def _contact(row) -> ContactOut:
    return ContactOut(
        contact_id=row.contact_id,
        name=row.name,
        email=row.email,
        group_name=row.group_name,
        active=bool(row.active),
    )


def _template(row) -> EmailTemplateOut:
    return EmailTemplateOut(
        template_id=row.template_id,
        name=row.name,
        to_group=row.to_group,
        cc_group=row.cc_group,
        subject_tmpl=row.subject_tmpl,
        body_tmpl=row.body_tmpl,
        is_html=bool(row.is_html),
        active=bool(row.active),
    )


def _component_type(row) -> ComponentTypeOut:
    return ComponentTypeOut(type_id=row.type_id, name=row.name, slot_key=row.slot_key, active=bool(row.active))


def _component(row) -> ComponentOut:
    return ComponentOut(
        component_id=row.component_id,
        type_id=row.type_id,
        type_name=row.type_name,
        slot_key=row.slot_key,
        code=row.code,
        description=row.description,
        unit=row.unit,
        active=bool(row.active),
    )


def _property(row) -> PropertiesOut:
    return PropertiesOut(
        property_id=row.property_id,
        name=row.name,
        unit=row.unit,
        active=bool(row.active),
        sort_order=(int(row.sort_order) if row.sort_order is not None else None),
    )


def _tolerance(row) -> ToleranceOut:
    return ToleranceOut(
        tolerance_id=row.tolerance_id,
        property_id=row.property_id,
        material_id=row.material_id,
        warn_low=row.warn_low,
        warn_high=row.warn_high,
        alarm_low=row.alarm_low,
        alarm_high=row.alarm_high,
        reference_value=row.reference_value,
        warn_low_input=row.warn_low_input,
        warn_low_mode=row.warn_low_mode,
        warn_high_input=row.warn_high_input,
        warn_high_mode=row.warn_high_mode,
        alarm_low_input=row.alarm_low_input,
        alarm_low_mode=row.alarm_low_mode,
        alarm_high_input=row.alarm_high_input,
        alarm_high_mode=row.alarm_high_mode,
        is_custom=row.is_custom,
    )


@router.get("/materials", response_model=list[MaterialOut], dependencies=[can_edit])
def materials(con=Depends(get_db), state=Depends(get_state), _session=Depends(get_session)):
    return [_material(row) for row in service.materials(con, subsidiary_id=state.subsidiary_id)]


@router.post("/materials", response_model=MaterialOut, dependencies=[can_edit])
def create_material(payload: MaterialUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _material(service.save_material(con, material_id=None, payload=payload))


@router.put("/materials/{material_id}", response_model=MaterialOut, dependencies=[can_edit])
def update_material(material_id: int, payload: MaterialUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _material(_not_found(lambda: service.save_material(con, material_id=material_id, payload=payload)))


@router.delete("/materials/{material_id}", status_code=204, dependencies=[can_edit])
def remove_material(material_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_material(con, material_id=material_id))


@router.get("/contacts", response_model=list[ContactOut], dependencies=[can_edit])
def contacts(con=Depends(get_db), _session=Depends(get_session)):
    return [_contact(row) for row in service.contacts(con)]


@router.post("/contacts", response_model=ContactOut, dependencies=[can_edit])
def create_contact(payload: ContactUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _contact(service.save_contact(con, contact_id=None, payload=payload))


@router.put("/contacts/{contact_id}", response_model=ContactOut, dependencies=[can_edit])
def update_contact(contact_id: int, payload: ContactUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _contact(_not_found(lambda: service.save_contact(con, contact_id=contact_id, payload=payload)))


@router.delete("/contacts/{contact_id}", status_code=204, dependencies=[can_edit])
def remove_contact(contact_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_contact(con, contact_id=contact_id))


@router.get("/email-templates", response_model=list[EmailTemplateOut], dependencies=[can_edit])
def templates(con=Depends(get_db), _session=Depends(get_session)):
    return [_template(row) for row in service.templates(con)]


@router.post("/email-templates", response_model=EmailTemplateOut, dependencies=[can_edit])
def create_template(payload: EmailTemplateUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _template(service.save_template(con, template_id=None, payload=payload))


@router.put("/email-templates/{template_id}", response_model=EmailTemplateOut, dependencies=[can_edit])
def update_template(template_id: int, payload: EmailTemplateUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _template(_not_found(lambda: service.save_template(con, template_id=template_id, payload=payload)))


@router.delete("/email-templates/{template_id}", status_code=204, dependencies=[can_edit])
def remove_template(template_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_template(con, template_id=template_id))


@router.get("/component-types", response_model=list[ComponentTypeOut], dependencies=[can_edit])
def component_types(con=Depends(get_db), _session=Depends(get_session)):
    return [_component_type(row) for row in service.component_types(con)]


@router.post("/component-types", response_model=ComponentTypeOut, dependencies=[can_edit])
def create_component_type(payload: ComponentTypeUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _component_type(service.save_component_type(con, type_id=None, payload=payload))


@router.put("/component-types/{type_id}", response_model=ComponentTypeOut, dependencies=[can_edit])
def update_component_type(type_id: int, payload: ComponentTypeUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _component_type(_not_found(lambda: service.save_component_type(con, type_id=type_id, payload=payload)))


@router.delete("/component-types/{type_id}", status_code=204, dependencies=[can_edit])
def remove_component_type(type_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_component_type(con, type_id=type_id))


@router.get("/components", response_model=list[ComponentOut], dependencies=[can_edit])
def components(con=Depends(get_db), _session=Depends(get_session)):
    return [_component(row) for row in service.components(con)]


@router.post("/components", response_model=ComponentOut, dependencies=[can_edit])
def create_component(payload: ComponentUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _component(service.save_component(con, component_id=None, payload=payload))


@router.put("/components/{component_id}", response_model=ComponentOut, dependencies=[can_edit])
def update_component(component_id: int, payload: ComponentUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _component(_not_found(lambda: service.save_component(con, component_id=component_id, payload=payload)))


@router.delete("/components/{component_id}", status_code=204, dependencies=[can_edit])
def remove_component(component_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_component(con, component_id=component_id))


@router.get("/properties", response_model=list[PropertiesOut], dependencies=[can_edit])
def properties(con=Depends(get_db), _session=Depends(get_session)):
    return [_property(row) for row in service.properties(con)]


@router.post("/properties", response_model=PropertiesOut, dependencies=[can_edit])
def create_property(payload: PropertyUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _property(service.save_property(con, property_id=None, payload=payload))


@router.put("/properties/{property_id}", response_model=PropertiesOut, dependencies=[can_edit])
def update_property(property_id: int, payload: PropertyUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    return _property(_not_found(lambda: service.save_property(con, property_id=property_id, payload=payload)))


@router.delete("/properties/{property_id}", status_code=204, dependencies=[can_edit])
def remove_property(property_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_property(con, property_id=property_id))


@router.get("/tolerances", response_model=list[ToleranceOut], dependencies=[can_edit])
def tolerances(con=Depends(get_db), _session=Depends(get_session)):
    return [_tolerance(row) for row in service.tolerances(con)]


@router.post("/tolerances", response_model=ToleranceOut, dependencies=[can_edit])
def create_tolerance(payload: ToleranceUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    try:
        return _tolerance(service.save_tolerance(con, tolerance_id=None, payload=payload))
    except ToleranceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/tolerances/{tolerance_id}", response_model=ToleranceOut, dependencies=[can_edit])
def update_tolerance(tolerance_id: int, payload: ToleranceUpsertRequest, con=Depends(get_serialized_db), _session=Depends(get_session)):
    try:
        return _tolerance(_not_found(lambda: service.save_tolerance(con, tolerance_id=tolerance_id, payload=payload)))
    except ToleranceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/tolerances/{tolerance_id}", status_code=204, dependencies=[can_edit])
def remove_tolerance(tolerance_id: int, con=Depends(get_serialized_db), _session=Depends(get_session)):
    _not_found(lambda: service.delete_tolerance(con, tolerance_id=tolerance_id))
