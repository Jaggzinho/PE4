from __future__ import annotations

from datetime import date

from backend.app.models.domain import EmailDraft, SinotticoRow
from backend.app.services.notifications import NotificationService
from pe3_qc_app.db.repos.outlook_repo import log_sample_request
from pe3_qc_app.db.repos.sample_queue_repo import clear_queue, enqueue_item, list_queue_rows, remove_item
from pe3_qc_app.db.repos.settings_repo import get_json
from pe3_qc_app.db.repos.sinottico_repo import list_dashboard_rows
from pe3_qc_app.db.repos.tests_repo import create_test_for_sample_request
from pe3_qc_app.services.rating_service import compute_ratings_for_materials
from pe3_qc_app.services.sinottico_status import compute_status


class EmptyQueueError(RuntimeError):
    pass


class SinotticoService:
    def __init__(self, notifications: NotificationService | None = None) -> None:
        self.notifications = notifications or NotificationService()

    def dashboard(self, con, *, today: date | None = None) -> list[SinotticoRow]:
        rows = list_dashboard_rows(con)
        thresholds = get_json(con, "sinottico_thresholds", {"green_days": 90, "yellow_days": 180})
        green_days = int(thresholds.get("green_days", 90))
        yellow_days = int(thresholds.get("yellow_days", 180))
        material_ids = sorted({int(row.material_id) for row in rows if row.material_id is not None})
        ratings = compute_ratings_for_materials(con, material_ids=material_ids) if material_ids else {}
        current_date = today or date.today()

        output = []
        for row in rows:
            status = compute_status(
                today=current_date,
                last_request_date=row.last_request_date,
                green_days=green_days,
                yellow_days=yellow_days,
            )
            output.append(
                SinotticoRow(
                    item_id=row.item_id,
                    machine_code=row.machine_code,
                    excel_code=row.excel_code,
                    description=row.description,
                    material_id=row.material_id,
                    material_code=row.material_code,
                    lastrina_code=row.lastrina_code,
                    last_request_date=row.last_request_date,
                    days_since=status.days_since,
                    status_level=status.level,
                    status_color=status.color,
                    rating_percent=(
                        ratings.get(int(row.material_id)) if row.material_id is not None else None
                    ),
                )
            )
        return output

    def queue(self, con, *, user_id: int):
        return list_queue_rows(con, user_id=user_id)

    def enqueue(self, con, *, user_id: int, item_id: int) -> None:
        enqueue_item(con, user_id=user_id, item_id=item_id)

    def remove(self, con, *, user_id: int, item_id: int) -> None:
        remove_item(con, user_id=user_id, item_id=item_id)

    def clear(self, con, *, user_id: int) -> None:
        clear_queue(con, user_id=user_id)

    def email_preview(self, con, *, user_id: int, username: str, locale: str) -> EmailDraft:
        rows = self.queue(con, user_id=user_id)
        if not rows:
            raise EmptyQueueError
        return self.notifications.queue_preview(
            con,
            queue_rows=rows,
            locale=locale,
            requester_name=username,
        )

    def finalize(self, con, *, user_id: int, username: str, locale: str) -> tuple[int, int]:
        rows = self.queue(con, user_id=user_id)
        if not rows:
            return 0, 0
        draft = self.notifications.queue_preview(
            con,
            queue_rows=rows,
            locale=locale,
            requester_name=username,
        )
        logged = 0
        created = 0
        today = date.today()
        for row in rows:
            request_id = log_sample_request(
                con,
                item_id=int(row.item_id),
                requested_by=user_id,
                outcome="sent",
                subject=draft.subject,
                to_list=draft.to_list,
                cc_list=draft.cc_list,
            )
            logged += 1
            try:
                test_id = create_test_for_sample_request(
                    con,
                    item_id=int(row.item_id),
                    req_id=int(request_id),
                    request_date=today,
                    requested_by=user_id,
                )
                if test_id is not None:
                    created += 1
            except Exception:
                # Preserve the desktop behavior: a logged request remains valid
                # even when a duplicate or incompatible test cannot be created.
                pass
        clear_queue(con, user_id=user_id)
        return logged, created
