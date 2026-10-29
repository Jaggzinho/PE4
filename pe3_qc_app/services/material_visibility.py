from __future__ import annotations

from collections.abc import Iterable

from pe3_qc_app.core.subsidiaries import normalize_subsidiary_id
from pe3_qc_app.db.repos.settings_repo import get_json, set_json


SETTING_VISIBLE_MATERIAL_CODES = "visible_material_codes"


_DEFAULT_WHITELISTS: dict[str, list[str]] = {
    "tcm_ro": [
        "438014255",
        "438014261",
        "438011103",
        "438014260",
        "438020339",
        "438014259",
        "438044935",
        "438014257",
        "438014258",
        "438019965",
    ],
    "wam_ro": [
        "438011598",
        "438011103",
    ],
    "tcm_it": [],
    "wam_wuxi": [],
}


def get_visible_material_codes(con, *, subsidiary_id: str) -> list[str]:
    """
    Returns the configured material-code whitelist for the subsidiary.

    Storage format: a plain JSON list of strings (legacy-friendly).
    If the setting is missing, it is auto-seeded with defaults.
    """
    sid = normalize_subsidiary_id(subsidiary_id)
    cfg = get_json(con, SETTING_VISIBLE_MATERIAL_CODES, None)
    if cfg is None:
        seeded = list(_DEFAULT_WHITELISTS.get(sid, []))
        set_json(con, SETTING_VISIBLE_MATERIAL_CODES, seeded)
        return seeded

    if isinstance(cfg, dict) and "codes" in cfg:
        return _norm_codes(cfg.get("codes"))
    if isinstance(cfg, list):
        return _norm_codes(cfg)
    return []


def get_visible_material_ids(con, *, subsidiary_id: str) -> set[int]:
    """
    Visibility rule:
    1) If whitelist is non-empty => only those materials.code are visible.
    2) Otherwise => materials referenced by active SINOTTICO rows are visible.
    """
    codes = get_visible_material_codes(con, subsidiary_id=subsidiary_id)
    if codes:
        placeholders = ", ".join(["?"] * len(codes))
        rows = con.execute(
            f"SELECT material_id FROM materials WHERE code IN ({placeholders})",
            list(codes),
        ).fetchall()
        return {int(r[0]) for r in rows if r and r[0] is not None}

    rows = con.execute(
        """
        SELECT DISTINCT material_id
        FROM sinottico_items
        WHERE active AND material_id IS NOT NULL
        """
    ).fetchall()
    return {int(r[0]) for r in rows if r and r[0] is not None}


def _norm_codes(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, Iterable):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for v in raw:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

