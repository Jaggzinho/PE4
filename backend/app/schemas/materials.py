from pydantic import BaseModel, Field

from backend.app.schemas.ids import ApiId


class MaterialComponentDefaultOut(BaseModel):
    code: str | None = None
    desc: str | None = None


class MaterialOut(BaseModel):
    material_id: ApiId
    code: str
    description: str | None
    lastrina_code: str | None
    lastrina_desc: str | None
    active: bool
    component_defaults: dict[str, MaterialComponentDefaultOut] = Field(default_factory=dict)


__all__ = ["MaterialComponentDefaultOut", "MaterialOut"]
