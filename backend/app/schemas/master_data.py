from typing import Literal

from pydantic import BaseModel, Field

ToleranceMode = Literal["absolute", "percent"]

from backend.app.schemas.materials import MaterialOut
from backend.app.schemas.ids import ApiId
from backend.app.schemas.validation import NonBlankStr


class MaterialUpsertRequest(BaseModel):
    code: NonBlankStr
    description: str | None = None
    lastrina_code: str | None = None
    lastrina_desc: str | None = None
    active: bool = True


class ContactOut(BaseModel):
    contact_id: ApiId
    name: str | None
    email: str
    group_name: str
    active: bool


class ContactUpsertRequest(BaseModel):
    name: str | None = None
    email: str = Field(min_length=3, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    group_name: NonBlankStr
    active: bool = True


class EmailTemplateOut(BaseModel):
    template_id: ApiId
    name: str
    to_group: str | None
    cc_group: str | None
    subject_tmpl: str
    body_tmpl: str
    is_html: bool
    active: bool


class EmailTemplateUpsertRequest(BaseModel):
    name: NonBlankStr
    to_group: str | None = None
    cc_group: str | None = None
    subject_tmpl: NonBlankStr
    body_tmpl: NonBlankStr
    is_html: bool = False
    active: bool = True


class ComponentTypeOut(BaseModel):
    type_id: ApiId
    name: str
    slot_key: str | None
    active: bool


class ComponentTypeUpsertRequest(BaseModel):
    name: NonBlankStr
    slot_key: str | None = None
    active: bool = True


class ComponentOut(BaseModel):
    component_id: ApiId
    type_id: ApiId
    type_name: str
    slot_key: str | None
    code: str
    description: str | None
    unit: str | None
    active: bool


class ComponentUpsertRequest(BaseModel):
    type_id: int
    code: NonBlankStr
    description: str | None = None
    unit: str | None = None
    active: bool = True


class PropertiesOut(BaseModel):
    property_id: ApiId
    name: str
    unit: str | None
    active: bool
    sort_order: int | None


class PropertyUpsertRequest(BaseModel):
    name: NonBlankStr
    unit: str | None = None
    active: bool = True
    sort_order: int | None = None


class ToleranceOut(BaseModel):
    tolerance_id: ApiId
    property_id: ApiId
    material_id: ApiId | None
    warn_low: float | None
    warn_high: float | None
    alarm_low: float | None
    alarm_high: float | None
    reference_value: float | None = None
    warn_low_input: float | None = None
    warn_low_mode: ToleranceMode = "absolute"
    warn_high_input: float | None = None
    warn_high_mode: ToleranceMode = "absolute"
    alarm_low_input: float | None = None
    alarm_low_mode: ToleranceMode = "absolute"
    alarm_high_input: float | None = None
    alarm_high_mode: ToleranceMode = "absolute"
    is_custom: bool = False


class ToleranceUpsertRequest(BaseModel):
    property_id: int
    material_id: int | None = None
    warn_low: float | None = None
    warn_high: float | None = None
    alarm_low: float | None = None
    alarm_high: float | None = None
    reference_value: float | None = None
    warn_low_input: float | None = None
    warn_low_mode: ToleranceMode = "absolute"
    warn_high_input: float | None = None
    warn_high_mode: ToleranceMode = "absolute"
    alarm_low_input: float | None = None
    alarm_low_mode: ToleranceMode = "absolute"
    alarm_high_input: float | None = None
    alarm_high_mode: ToleranceMode = "absolute"


__all__ = [
    "ComponentOut",
    "ComponentTypeOut",
    "ComponentTypeUpsertRequest",
    "ComponentUpsertRequest",
    "ContactOut",
    "ContactUpsertRequest",
    "EmailTemplateOut",
    "EmailTemplateUpsertRequest",
    "MaterialOut",
    "MaterialUpsertRequest",
    "PropertiesOut",
    "PropertyUpsertRequest",
    "ToleranceOut",
    "ToleranceUpsertRequest",
]
