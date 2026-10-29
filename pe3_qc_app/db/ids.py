from __future__ import annotations

import secrets


def new_id() -> int:
    # DuckDB BIGINT signed: keep within 63 bits.
    return int(secrets.randbits(63))

