from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_db, get_session, get_state
from backend.app.schemas.ratings import RatingOverviewOut, RatingPointOut
from backend.app.services.ratings import (
    InvalidRatingDateRangeError,
    RatingMaterialNotFoundError,
    RatingService,
)


router = APIRouter(prefix="/ratings", tags=["ratings"])
service = RatingService()


@router.get("", response_model=RatingOverviewOut)
def ratings_overview(
    material_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    con=Depends(get_db),
    state=Depends(get_state),
    _session=Depends(get_session),
):
    try:
        overview = service.overview(
            con,
            subsidiary_id=state.subsidiary_id,
            material_id=int(material_id),
            date_from=date_from,
            date_to=date_to,
        )
    except RatingMaterialNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    except InvalidRatingDateRangeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return RatingOverviewOut(
        material_id=overview.material_id,
        configured=overview.configured,
        date_min=overview.date_min,
        date_max=overview.date_max,
        date_from=overview.date_from,
        date_to=overview.date_to,
        points=[
            RatingPointOut(date=point.date, rating_percent=point.rating_percent)
            for point in overview.points
        ],
        latest_rating=overview.latest_rating,
        average_rating=overview.average_rating,
    )
