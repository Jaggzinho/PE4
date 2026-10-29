from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_db, get_session
from backend.app.schemas.calendar import (
    CalendarItemOut,
    CalendarMonthOut,
    QcFailureOut,
    QcFailureReportOut,
)
from backend.app.services.calendar import CalendarService, CalendarTestNotFoundError


router = APIRouter(prefix="/calendar", tags=["calendar"])
service = CalendarService()


@router.get("", response_model=CalendarMonthOut)
def calendar_month(
    year: int = Query(ge=1900, le=9999),
    month: int = Query(ge=1, le=12),
    con=Depends(get_db),
    _session=Depends(get_session),
):
    result = service.month(con, year=int(year), month=int(month))
    return CalendarMonthOut(
        year=result.year,
        month=result.month,
        date_from=result.date_from,
        date_to=result.date_to,
        items=[CalendarItemOut(**item.__dict__) for item in result.items],
    )


@router.get("/tests/{test_id}/failures", response_model=QcFailureReportOut)
def test_failures(
    test_id: int,
    con=Depends(get_db),
    _session=Depends(get_session),
):
    try:
        report = service.failures(con, test_id=int(test_id))
    except CalendarTestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return QcFailureReportOut(
        test_id=report.test_id,
        material_code=report.material_code,
        request_date=report.request_date,
        failures=[QcFailureOut(**failure.__dict__) for failure in report.failures],
    )
