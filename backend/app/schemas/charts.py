from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from backend.app.schemas.ids import ApiId


class ChartTraceOut(BaseModel):
    name: str
    x: list[str]
    y: list[float]


class ChartsResponse(BaseModel):
    material_id: ApiId
    date_from: date | None
    date_to: date | None
    traces: list[ChartTraceOut]


class ChartsTolerancePctOut(BaseModel):
    warn_pct: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    alarm_pct: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ChartsConfigOut(BaseModel):
    tolerance_pct: ChartsTolerancePctOut
    fixed_properties: list[tuple[ApiId | None, str, str]]
    defaults: dict[str, bool] = Field(default_factory=dict)


class PanelTraceOut(BaseModel):
    name: str
    x: list[str]
    y: list[float]
    kind: str = "series"


class ChartPanelOut(BaseModel):
    property_id: ApiId | None
    title: str
    unit: str | None = None
    traces: list[PanelTraceOut]


class ChartsPanelsResponse(BaseModel):
    material_id: ApiId
    date_from: date | None
    date_to: date | None
    panels: list[ChartPanelOut]


__all__ = [
    "ChartPanelOut",
    "ChartsConfigOut",
    "ChartsPanelsResponse",
    "ChartsResponse",
    "ChartsTolerancePctOut",
    "ChartTraceOut",
    "PanelTraceOut",
]
