from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from backend.app.schemas.ids import ApiId


class CalendarItemOut(BaseModel):
    test_id: ApiId
    material_id: ApiId
    material_code: str
    material_desc: str | None
    lastrina_code: str | None
    prod_date: date
    rating_percent: float | None


class CalendarMonthOut(BaseModel):
    year: int
    month: int
    date_from: date
    date_to: date
    items: list[CalendarItemOut]


class QcFailureOut(BaseModel):
    property_name: str
    actual_value: str


class QcFailureReportOut(BaseModel):
    test_id: ApiId
    material_code: str
    request_date: date | None
    failures: list[QcFailureOut]


__all__ = ["CalendarItemOut", "CalendarMonthOut", "QcFailureOut", "QcFailureReportOut"]
