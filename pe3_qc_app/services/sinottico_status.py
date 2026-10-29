from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SinotticoStatus:
    days_since: int | None
    level: str  # "green" | "yellow" | "red" | "none"
    color: str


def compute_status(*, today: date, last_request_date: date | None, green_days: int, yellow_days: int) -> SinotticoStatus:
    if last_request_date is None:
        return SinotticoStatus(days_since=None, level="none", color="#94a3b8")
    days = int((today - last_request_date).days)
    if days <= int(green_days):
        return SinotticoStatus(days_since=days, level="green", color="#16a34a")
    if days <= int(yellow_days):
        return SinotticoStatus(days_since=days, level="yellow", color="#f59e0b")
    return SinotticoStatus(days_since=days, level="red", color="#dc2626")

