from __future__ import annotations

import re
from typing import Any


def norm_header(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).replace("\u00A0", " ")
    return re.sub(r"\s+", " ", s.strip().lower())


def col_index(headers_norm: list[str], name: str) -> int | None:
    key = norm_header(name)
    try:
        return headers_norm.index(key)
    except ValueError:
        return None
