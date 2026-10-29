from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.imports import ImportResultOut


class JobOut(BaseModel):
    job_id: str
    kind: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int = Field(ge=0, le=100)
    messages: list[str]
    result: ImportResultOut | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreatedOut(BaseModel):
    job_id: str
    status: Literal["queued", "running"]
