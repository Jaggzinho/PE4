from __future__ import annotations

from datetime import date

from backend.app.models.domain import RatingOverview, RatingPoint
from pe3_qc_app.db.repos.materials_repo import get_material
from pe3_qc_app.services.chart_data import fetch_date_bounds
from pe3_qc_app.services.material_visibility import get_visible_material_ids
from pe3_qc_app.services.rating_service import fetch_rating_series, has_rating_configuration


class RatingMaterialNotFoundError(LookupError):
    pass


class InvalidRatingDateRangeError(ValueError):
    pass


class RatingService:
    def overview(
        self,
        con,
        *,
        subsidiary_id: str,
        material_id: int,
        date_from: date | None,
        date_to: date | None,
    ) -> RatingOverview:
        material = get_material(con, material_id=int(material_id))
        visible = get_visible_material_ids(con, subsidiary_id=subsidiary_id)
        if material is None or not material.active or int(material_id) not in visible:
            raise RatingMaterialNotFoundError

        if date_from is not None and date_to is not None and date_from > date_to:
            raise InvalidRatingDateRangeError("date_from must be on or before date_to")

        date_min, date_max = fetch_date_bounds(con, material_id=int(material_id))
        effective_from = date_from if date_from is not None else date_min
        effective_to = date_to if date_to is not None else date_max
        if effective_from is not None and effective_to is not None and effective_from > effective_to:
            raise InvalidRatingDateRangeError("date_from must be on or before date_to")
        configured = has_rating_configuration(con, material_id=int(material_id))

        raw_points = []
        if configured and effective_from is not None and effective_to is not None:
            raw_points = fetch_rating_series(
                con,
                material_id=int(material_id),
                date_from=effective_from,
                date_to=effective_to,
            )
        points = [RatingPoint(date=point_date, rating_percent=float(value)) for point_date, value in raw_points]
        values = [point.rating_percent for point in points]

        return RatingOverview(
            material_id=int(material_id),
            configured=configured,
            date_min=date_min,
            date_max=date_max,
            date_from=effective_from,
            date_to=effective_to,
            points=points,
            latest_rating=values[-1] if values else None,
            average_rating=(sum(values) / len(values)) if values else None,
        )
