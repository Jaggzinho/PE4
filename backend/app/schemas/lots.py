from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from backend.app.schemas.ids import ApiId


class ComponentLotIn(BaseModel):
    code: str | None = None
    desc: str | None = None
    lot: str | None = None


class LotsRowOut(BaseModel):
    test_id: ApiId
    material_id: ApiId
    material_code: str
    material_desc: str | None
    lastrina_code: str | None
    request_date: date | None
    prod_date: date | None
    analysis_date: date | None
    iso_code: str | None
    iso_desc: str | None
    iso_lot: str | None
    pol_code: str | None
    pol_desc: str | None
    pol_lot: str | None
    cat_code: str | None
    cat_desc: str | None
    cat_lot: str | None
    add1_code: str | None
    add1_desc: str | None
    add1_lot: str | None
    add2_code: str | None
    add2_desc: str | None
    add2_lot: str | None
    durezza: str | None
    carico_rottura: str | None
    allungamento: str | None
    lacerazione_ba: str | None
    lacerazione_ca: str | None
    abrasione: str | None
    resistivita_superficiale: str | None


class LotsPageOut(BaseModel):
    items: list[LotsRowOut]
    total: int
    limit: int
    offset: int
    has_next: bool


class LotDetailsOut(BaseModel):
    test_id: ApiId
    material_id: ApiId
    request_date: date | None
    prod_date: date | None
    analysis_date: date | None
    components: dict[str, ComponentLotIn]
    qc: dict[str, str | None]


class LotUpsertRequest(BaseModel):
    material_id: int
    request_date: date | None = None
    prod_date: date | None = None
    analysis_date: date | None = None
    components: dict[str, ComponentLotIn] = Field(default_factory=dict)
    qc: dict[str, str | None] = Field(default_factory=dict)


__all__ = ["ComponentLotIn", "LotDetailsOut", "LotsPageOut", "LotsRowOut", "LotUpsertRequest"]
