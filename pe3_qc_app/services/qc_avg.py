from __future__ import annotations

from pe3_qc_app.services.parse import parse_float


def avg_of_texts(texts: list[str], *, decimals: int = 2) -> str | None:
    values: list[float] = []
    for t in texts:
        s = (t or "").strip()
        if not s:
            continue
        num = parse_float(s)
        if num is None:
            raise ValueError(f"Invalid numeric value: {s!r}")
        values.append(float(num))

    if not values:
        return None

    avg = sum(values) / float(len(values))
    return f"{avg:.{int(decimals)}f}"

