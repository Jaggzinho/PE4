from __future__ import annotations

import json
from typing import Any


def get_json(con, key: str, default: Any) -> Any:
    row = con.execute("SELECT value_json FROM settings WHERE key = ?", [key]).fetchone()
    if row is None:
        return default
    try:
        return json.loads(str(row[0]))
    except Exception:
        return default


def set_json(con, key: str, value: Any) -> None:
    con.execute(
        "INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
        [key, json.dumps(value)],
    )

