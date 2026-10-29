from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ChartTrace:
    name: str
    x: list[str]
    y: list[float]
    kind: str = "series"


@dataclass(frozen=True)
class ChartPanel:
    property_id: int | None
    title: str
    unit: str | None
    traces: list[ChartTrace] = field(default_factory=list)


@dataclass(frozen=True)
class SinotticoRow:
    item_id: int
    machine_code: str | None
    excel_code: str | None
    description: str | None
    material_id: int | None
    material_code: str | None
    lastrina_code: str | None
    last_request_date: date | None
    days_since: int | None
    status_level: str | None
    status_color: str | None
    rating_percent: float | None


@dataclass(frozen=True)
class EmailDraft:
    to_list: str
    cc_list: str
    subject: str
    body: str
    is_html: bool


@dataclass(frozen=True)
class RatingSetting:
    property_id: int
    property_name: str
    unit: str | None
    weight: float
    rule_json: str | None


@dataclass(frozen=True)
class RatingPoint:
    date: date
    rating_percent: float


@dataclass(frozen=True)
class RatingOverview:
    material_id: int
    configured: bool
    date_min: date | None
    date_max: date | None
    date_from: date | None
    date_to: date | None
    points: list[RatingPoint]
    latest_rating: float | None
    average_rating: float | None


@dataclass(frozen=True)
class CalendarItem:
    test_id: int
    material_id: int
    material_code: str
    material_desc: str | None
    lastrina_code: str | None
    prod_date: date
    rating_percent: float | None


@dataclass(frozen=True)
class CalendarMonth:
    year: int
    month: int
    date_from: date
    date_to: date
    items: list[CalendarItem]


@dataclass(frozen=True)
class QcFailure:
    property_name: str
    actual_value: str


@dataclass(frozen=True)
class QcFailureReport:
    test_id: int
    material_code: str
    request_date: date | None
    failures: list[QcFailure]
