from pydantic import BaseModel, Field


class ImportResultOut(BaseModel):
    materials: int
    properties: int
    tests: int
    measurements: int
    sinottico_items: int
    component_types: int
    components: int
    material_component_defaults: int


class ImportXlsmResponse(BaseModel):
    logs: list[str] = Field(default_factory=list)
    result: ImportResultOut


__all__ = ["ImportResultOut", "ImportXlsmResponse"]
