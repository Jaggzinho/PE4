from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from backend.app.schemas.ids import ApiId


class SinotticoRowOut(BaseModel):
    item_id: ApiId
    machine_code: str | None
    excel_code: str | None
    description: str | None
    material_id: ApiId | None
    material_code: str | None
    lastrina_code: str | None
    last_request_date: date | None
    days_since: int | None = None
    status_level: str | None = None
    status_color: str | None = None
    rating_percent: float | None = None


class QueueRowOut(BaseModel):
    item_id: ApiId
    machine_code: str | None
    material_code: str | None
    description: str | None
    lastrina_code: str | None
    last_request_date: date | None


class EmailDraftOut(BaseModel):
    to_list: str
    cc_list: str
    subject: str
    body: str
    is_html: bool


class FinalizeQueueResponse(BaseModel):
    sample_requests_logged: int
    tests_created: int


__all__ = ["EmailDraftOut", "FinalizeQueueResponse", "QueueRowOut", "SinotticoRowOut"]
