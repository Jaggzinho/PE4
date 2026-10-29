from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subsidiary:
    subsidiary_id: str
    label: str
    flag_key: str  # "it" | "ro" | "cn"


SUBSIDIARIES: tuple[Subsidiary, ...] = (
    Subsidiary("tcm_ro", "TCM Romania", "ro"),
    Subsidiary("tcm_it", "TCM Italia", "it"),
    Subsidiary("wam_ro", "WAM Romania", "ro"),
    Subsidiary("wam_wuxi", "WAM Wuxi", "cn"),
)

DEFAULT_SUBSIDIARY_ID = "tcm_ro"
_KNOWN_IDS = {s.subsidiary_id for s in SUBSIDIARIES}


def normalize_subsidiary_id(raw: str | None) -> str:
    if not raw:
        return DEFAULT_SUBSIDIARY_ID
    s = str(raw).strip().lower()
    return s if s in _KNOWN_IDS else DEFAULT_SUBSIDIARY_ID


def default_db_filename(*, subsidiary_id: str) -> str:
    subsidiary_id = normalize_subsidiary_id(subsidiary_id)
    return f"qc_{subsidiary_id}.duckdb"

