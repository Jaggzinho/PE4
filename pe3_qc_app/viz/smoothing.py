from __future__ import annotations

from datetime import date, datetime, time

import matplotlib.dates as mdates
import numpy as np


def smooth_pchip(
    xs: list[date],
    ys: list[float],
    *,
    samples_per_segment: int = 8,
) -> tuple[list[datetime], list[float]]:
    raw_dt = [_to_dt(d) for d in xs]
    if len(raw_dt) != len(ys):
        return raw_dt, list(ys)

    uniq_dt, uniq_ys = _aggregate_duplicate_dates(raw_dt, ys)
    if len(uniq_dt) < 2:
        return raw_dt, list(ys)

    x = np.asarray([float(mdates.date2num(d)) for d in uniq_dt], dtype=float)
    y = np.asarray(uniq_ys, dtype=float)

    dx = np.diff(x)
    if np.any(dx <= 0):
        return raw_dt, list(ys)

    if len(x) < 4:
        return _dense_linear(x, y, samples_per_segment=samples_per_segment)

    h = dx
    delta = np.diff(y) / h
    n = len(x)
    m = np.zeros(n, dtype=float)

    m[0] = _pchip_endpoint_slope(h[0], h[1], delta[0], delta[1])
    m[-1] = _pchip_endpoint_slope(h[-1], h[-2], delta[-1], delta[-2])

    for i in range(1, n - 1):
        d0 = float(delta[i - 1])
        d1 = float(delta[i])
        if d0 == 0.0 or d1 == 0.0 or np.sign(d0) != np.sign(d1):
            m[i] = 0.0
            continue
        w1 = 2.0 * h[i] + h[i - 1]
        w2 = h[i] + 2.0 * h[i - 1]
        m[i] = (w1 + w2) / (w1 / d0 + w2 / d1)

    sps = max(2, int(samples_per_segment))
    x_dense: list[float] = []
    y_dense: list[float] = []
    for i in range(n - 1):
        xi = float(x[i])
        hi = float(h[i])
        t = np.linspace(0.0, 1.0, sps, endpoint=False)
        t2 = t * t
        t3 = t2 * t
        h00 = 2.0 * t3 - 3.0 * t2 + 1.0
        h10 = t3 - 2.0 * t2 + t
        h01 = -2.0 * t3 + 3.0 * t2
        h11 = t3 - t2
        yt = (h00 * y[i]) + (h10 * hi * m[i]) + (h01 * y[i + 1]) + (h11 * hi * m[i + 1])
        xt = xi + (t * hi)
        x_dense.extend(xt.tolist())
        y_dense.extend(yt.tolist())

    x_dense.append(float(x[-1]))
    y_dense.append(float(y[-1]))

    dt_dense = [mdates.num2date(v).replace(tzinfo=None) for v in x_dense]
    return dt_dense, [float(v) for v in y_dense]


def _to_dt(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _pchip_endpoint_slope(h0: float, h1: float, d0: float, d1: float) -> float:
    m0 = ((2.0 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if np.sign(m0) != np.sign(d0):
        return 0.0
    if np.sign(d0) != np.sign(d1) and abs(m0) > abs(3.0 * d0):
        return 3.0 * d0
    return float(m0)


def _aggregate_duplicate_dates(xs: list[datetime], ys: list[float]) -> tuple[list[datetime], list[float]]:
    by_x: dict[datetime, list[float]] = {}
    for x, y in zip(xs, ys, strict=False):
        by_x.setdefault(x, []).append(float(y))
    uniq_x = sorted(by_x.keys())
    uniq_y: list[float] = []
    for x in uniq_x:
        vals = by_x[x]
        uniq_y.append(float(sum(vals) / len(vals)))
    return uniq_x, uniq_y


def _dense_linear(
    x: np.ndarray,
    y: np.ndarray,
    *,
    samples_per_segment: int,
) -> tuple[list[datetime], list[float]]:
    sps = max(2, int(samples_per_segment))
    x_dense: list[float] = []
    y_dense: list[float] = []
    for i in range(len(x) - 1):
        xi = float(x[i])
        xj = float(x[i + 1])
        yi = float(y[i])
        yj = float(y[i + 1])
        xt = np.linspace(xi, xj, sps, endpoint=False)
        t = (xt - xi) / (xj - xi)
        yt = yi + (t * (yj - yi))
        x_dense.extend([float(v) for v in xt.tolist()])
        y_dense.extend([float(v) for v in yt.tolist()])
    x_dense.append(float(x[-1]))
    y_dense.append(float(y[-1]))
    dt_dense = [mdates.num2date(v).replace(tzinfo=None) for v in x_dense]
    return dt_dense, y_dense

