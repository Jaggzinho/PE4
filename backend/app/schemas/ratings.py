from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from backend.app.schemas.ids import ApiId


class RatingPointOut(BaseModel):
    date: date
    rating_percent: float


class RatingOverviewOut(BaseModel):
    material_id: ApiId
    configured: bool
    date_min: date | None
    date_max: date | None
    date_from: date | None
    date_to: date | None
    points: list[RatingPointOut]
    latest_rating: float | None
    average_rating: float | None


__all__ = ["RatingOverviewOut", "RatingPointOut"]
