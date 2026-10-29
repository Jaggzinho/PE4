from __future__ import annotations

from calendar import monthrange
from datetime import date

from backend.app.models.domain import (
    CalendarItem,
    CalendarMonth,
    QcFailure,
    QcFailureReport,
)
from pe3_qc_app.db.repos.calendar_repo import list_tests_by_prod_date_range
from pe3_qc_app.services.qc_failures_service import fetch_alarm_tolerance_failures
from pe3_qc_app.services.test_rating_service import compute_test_ratings


class CalendarTestNotFoundError(LookupError):
    pass


class CalendarService:
    def month(self, con, *, year: int, month: int) -> CalendarMonth:
        date_from = date(int(year), int(month), 1)
        date_to = date(int(year), int(month), monthrange(int(year), int(month))[1])
        rows = list_tests_by_prod_date_range(con, date_from=date_from, date_to=date_to)
        ratings = compute_test_ratings(
            con,
            tests=[(row.test_id, row.material_id) for row in rows],
        )
        return CalendarMonth(
            year=int(year),
            month=int(month),
            date_from=date_from,
            date_to=date_to,
            items=[
                CalendarItem(
                    test_id=row.test_id,
                    material_id=row.material_id,
                    material_code=row.material_code,
                    material_desc=row.material_desc,
                    lastrina_code=row.lastrina_code,
                    prod_date=row.prod_date,
                    rating_percent=ratings.get(row.test_id),
                )
                for row in rows
            ],
        )

    def failures(self, con, *, test_id: int) -> QcFailureReport:
        try:
            context, rows = fetch_alarm_tolerance_failures(con, test_id=int(test_id))
        except ValueError as exc:
            raise CalendarTestNotFoundError from exc
        return QcFailureReport(
            test_id=context.test_id,
            material_code=context.material_code,
            request_date=context.request_date,
            failures=[
                QcFailure(property_name=row.property_name, actual_value=row.actual_value)
                for row in rows
            ],
        )
